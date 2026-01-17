from typing import Optional
from pydantic import BaseModel

class GameParameters(BaseModel):
    '''
    Класс для хранения параметров игрового мира.

    Attributes:
        word_settings: Описание игрового мира на естесственном языке.
        genre: Жанр игры (например: приключения / драма / ужасы).
        epoch: Исторический период или уровень развития технологий в игровом мире (например: средневековье / современность / будущее).
        tonality: Тональность игрового мира (например: сказочная / нейтральная / героическая).
    '''
    world_settings: str
    genre: str
    epoch: str
    tonality: str

class DialogParamters(BaseModel):
    '''  
    Класс для хранения настроек диалога.

    Attributes:
        scene: Описание окружения, в котором происходит диалог.
        context: Краткое содержание диалога.
        mn_depth: Минимальная глубина диалога.
        mx_depth: Максимальная глубина диалога.
        mn_answers_cnt: Минимальное количество вариантов ответов.
        mx_answers_cnt: Максимальное количество вариантов ответов.
        extra: Дополнительные параметры диалога.
    '''
    scene: str
    context: str
    mn_depth: int
    mx_depth: int
    mn_answers_cnt: int
    mx_answers_cnt: int
    # goals: list[GoalParameters]
    NPC_to_hero_relation: str
    hero_to_NPC_relation: str
    extra: str


# class GoalParameters(BaseModel):
#     type: str
#     object: str
#     condition: str

class CharacterParameters(BaseModel):
    '''
    Класс для хранения параметров персонажа (главного героя или NPC). 

    Attributes:
        name: Имя персонажа
        profession: Профессия
        talk_style: Стиль речи
        traits: Характер персонажа
        look: Внешний вид
        extra: Дополнительная характеристика
    '''
    name: str|None = None
    profession: str|None  = None
    talk_style: str|None = None
    traits: str|None = None
    look: str|None = None
    extra: str|None = None