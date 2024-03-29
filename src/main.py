import random
import json
import uuid
from typing import List, Union, Tuple
from pydantic import BaseModel

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

SURROUND_MATRIX = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


current_games_dict = {}


app = FastAPI(title='Игра Minesweeper', description='Тестовое задание - реализация REST API по заданной спецификации (Вячеслав Сипаков)')

#app.mount("/static", StaticFiles(directory="../static"), name="static")

templates = Jinja2Templates(directory="../templates")


class NewGameRequest(BaseModel):
    width: int
    height: int
    mines_count: int


class GameTurnRequest(BaseModel):
    game_id: str
    col: int
    row: int


class GameInfoResponse(BaseModel):
    game_id: str
    width: int
    height: int
    mines_count: int
    field: List[List[str]]
    completed: bool = False


class ErrorResponse(BaseModel):
    error: str


class GameErrorException(Exception):
    def __init__(self, name: str):
        self.name = name


@app.exception_handler(GameErrorException)
async def game_error_exception_handler(request: Request, exc: GameErrorException):
    return JSONResponse(
        status_code=400,
        content={"error": exc.name},
    )


def generate_game_fields(width: int, height: int, mines_count: int) -> Tuple[List[List[str]], List[List[str]]]:
    field = []
    scouted_field = []

    for i in range(height):
        row = []
        row_scouted = []
        for j in range(width):
            row.append(' ')
            row_scouted.append(' ')
        field.append(row)
        scouted_field.append(row_scouted)

    for i in range(mines_count):
        mine_x, mine_y = random.randint(0, width - 1), random.randint(0, height - 1)
        while field[mine_y][mine_x] != ' ':
            mine_x, mine_y = random.randint(0, width - 1), random.randint(0, height - 1)
        field[mine_y][mine_x] = 'M'

    count_mines_around_cells(field, width, height)

    return field, scouted_field


def convert_mines_to_x_marks(field: List[List[str]]) -> List[List[str]]:
    res_field: List[List[str]] = []

    for row in field:
        res_row: List[str] = []
        for cell in row:
            if cell == 'M':
                res_row.append('X')
            else:
                res_row.append(cell)
        res_field.append(res_row)
    return res_field


def count_uncleared_cells(scouted_field: List[List[str]]) -> int:
    uncleared_cells_count = 0
    for row in scouted_field:
        uncleared_cells_count += row.count(' ')
    return uncleared_cells_count


def count_mines_around_cells(field: List[List[str]], height: int, width: int) -> None:
    for i, row in enumerate(field):
        for j, cell in enumerate(field[i]):
            if cell == 'M':
                continue
            cell_val = 0
            for offset in SURROUND_MATRIX:
                neighbour_y, neighbour_x = (i + offset[0], j + offset[1])
                if 0 <= neighbour_y < height and 0 <= neighbour_x < width:
                    neighbour_cell = field[neighbour_y][neighbour_x]
                    if neighbour_cell == 'M':
                        cell_val += 1
            field[i][j] = str(cell_val)


def scout_empty_cells(scouted_field: List[List[str]], field: List[List[str]], width: int, height: int, x: int, y: int) -> None:
    for offset in SURROUND_MATRIX:
        neighbour_y, neighbour_x = y + offset[0], x + offset[1]
        if 0 <= neighbour_y < height and 0 <= neighbour_x < width:
            neighbour_cell_scouted = scouted_field[neighbour_y][neighbour_x]
            neighbour_cell = field[neighbour_y][neighbour_x]

            if neighbour_cell_scouted == ' ' and neighbour_cell != 'M':
                scouted_field[neighbour_y][neighbour_x] = neighbour_cell
                if neighbour_cell == '0':
                    scout_empty_cells(scouted_field, field, width, height, neighbour_x, neighbour_y)


async def debug_request_info(request: Request):
    print(f'request header       : {dict(request.headers.items())}')
    print(f'request query params : {dict(request.query_params.items())}')
    try:
        print(f'request json         : {await request.json()}')
    except Exception as err:
        # could not parse json
        print(f'request body         : {await request.body()}')


responses = {
    400: {'model': ErrorResponse, 'description': 'Ошибка запроса или некорректное действие'},
    200: {'model': GameInfoResponse, 'description': 'OK'},
}


@app.get("/", response_class=HTMLResponse)
async def get_game_client(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="game_client.html"
    )


@app.post("/api/new", responses=responses)
async def new_game(body: NewGameRequest, request: Request):
    #await debug_request_info(request)

    game_uuid = str(uuid.uuid4())

    if body.width > 30 or body.width < 2:
        raise GameErrorException('Ширина поля должна быть не менее 2 и не более 30')
    if body.height > 30 or body.height < 2:
        raise GameErrorException('Высота поля должна быть не менее 2 и не более 30')
    max_mines = body.width * body.height - 1
    if body.mines_count > max_mines or body.mines_count < 1:
        raise GameErrorException(f'Количество мин должно быть не менее 1 и не более {max_mines}')

    field, scouted_field = generate_game_fields(body.width, body.height, body.mines_count)

    #print(field)

    current_games_dict[game_uuid] = {
        "width": body.width,
        "height": body.height,
        "mines_count": body.mines_count,
        "completed": False,
        "field": field,
        "scouted_field": scouted_field,
    }

    return GameInfoResponse(game_id=game_uuid,
                            width=body.width,
                            height=body.height,
                            mines_count=body.mines_count,
                            completed=False,
                            field=scouted_field)


@app.post("/api/turn", responses=responses)
async def turn(body: GameTurnRequest, request: Request):
    #await debug_request_info(request)

    try:
        game_info = current_games_dict[body.game_id]
    except KeyError as exc:
        raise GameErrorException('Игра с таким id не найдена')
    if game_info['completed'] is True:
        raise GameErrorException('Игра завершена')
    if 0 <= body.row < game_info['height'] and 0 <= body.col < game_info['width']:
        if game_info['scouted_field'][body.row][body.col] != ' ':
            raise GameErrorException('Клетка уже открыта')
        if game_info['field'][body.row][body.col] == 'M':
            new_field = convert_mines_to_x_marks(game_info['field'])
            game_info['completed'] = True
            game_info['field'] = new_field
            game_info['scouted_field'] = new_field
            response = GameInfoResponse(game_id=body.game_id,
                                        width=game_info['width'],
                                        height=game_info['height'],
                                        mines_count=game_info['mines_count'],
                                        completed=True,
                                        field=new_field)
            #del current_games_dict[body.game_id]
            return response
        elif game_info['field'][body.row][body.col] == '0':
            game_info['scouted_field'][body.row][body.col] = game_info['field'][body.row][body.col]
            scout_empty_cells(game_info['scouted_field'], game_info['field'],
                              game_info['width'], game_info['height'],
                              body.col, body.row)
            if game_info['mines_count'] == count_uncleared_cells(game_info['scouted_field']):
                game_info['completed'] = True
                game_info['scouted_field'] = game_info['field']
                response = GameInfoResponse(game_id=body.game_id,
                                            width=game_info['width'],
                                            height=game_info['height'],
                                            mines_count=game_info['mines_count'],
                                            completed=True,
                                            field=game_info['field'])
                #del current_games_dict[body.game_id]
                return response
            else:
                return GameInfoResponse(game_id=body.game_id,
                                        width=game_info['width'],
                                        height=game_info['height'],
                                        mines_count=game_info['mines_count'],
                                        completed=False,
                                        field=game_info['scouted_field'])
        else:
            game_info['scouted_field'][body.row][body.col] = game_info['field'][body.row][body.col]
            if game_info['mines_count'] == count_uncleared_cells(game_info['scouted_field']):
                game_info['completed'] = True
                game_info['scouted_field'] = game_info['field']
                response = GameInfoResponse(game_id=body.game_id,
                                            width=game_info['width'],
                                            height=game_info['height'],
                                            mines_count=game_info['mines_count'],
                                            completed=True,
                                            field=game_info['field'])
                #del current_games_dict[body.game_id]
                return response
            else:
                return GameInfoResponse(game_id=body.game_id,
                                        width=game_info['width'],
                                        height=game_info['height'],
                                        mines_count=game_info['mines_count'],
                                        completed=False,
                                        field=game_info['scouted_field'])
    else:
        raise GameErrorException('Координаты за пределами поля')
