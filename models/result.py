from tortoise import fields, models
from datetime import datetime

class Result(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="results", description="Пользователь (ученик)")
    task = fields.ForeignKeyField("models.Task", related_name="results", description="Задание")
    score = fields.FloatField(null=True, description="Баллы (если тип задания — score)")
    time_seconds = fields.FloatField(null=True, description="Время в секундах (если тип задания — time)")
    confirmed = fields.BooleanField(default=False, description="Подтверждение (для физры)")
    confirmed_by = fields.ForeignKeyField("models.User", related_name="confirmed_results", null=True, description="Кто подтвердил")
    confirmation_date = fields.DatetimeField(null=True, description="Дата подтверждения")
    started_at = fields.DatetimeField(auto_now_add=True, description="Время начала задания")
    ended_at = fields.DatetimeField(null=True, description="Время окончания задания")

    class Meta:
        table = "results"

    def __str__(self):
        return f"Результат {self.id} для {self.user} по заданию {self.task}" 