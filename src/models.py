from peewee import *


db = SqliteDatabase('current_games.db')


class GameModel(Model):
    game_id = AutoField(unique=True, primary_key=True)
    width = IntegerField()
    height = IntegerField()
    mines_count = IntegerField()
    completed = BooleanField(default=False)
    field =

    def __str__(self):
        return 'Game ' + self.game_id

    class Meta:
        database = db


class GameFieldModel(Model):
    game_id =
