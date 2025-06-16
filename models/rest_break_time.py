from tortoise import fields, models
from datetime import datetime

class RestBreakTime(models.Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="rest_break_times", description="Пользователь")
    access_time = fields.DatetimeField(description="Время, когда откроется доступ к заданиям (UTC+4)")
    last_break_time = fields.DatetimeField(description="Время последнего перерыва (UTC+4)")
    total_work_time = fields.FloatField(default=0, description="Общее время работы после последнего перерыва (в секундах)")

    class Meta:
        table = "rest_break_time"

    def __str__(self):
        return f"Перерыв для {self.user} до {self.access_time}" 