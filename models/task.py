from tortoise import fields, models

class Task(models.Model):
    id = fields.IntField(pk=True)
    subjects_name = fields.CharField(max_length=255, description="Название предмета (например, 'Математика', 'Физкультура')")
    name = fields.CharField(max_length=255, description="Название задания")
    type = fields.CharField(max_length=50, description="Тип задания ('score' или 'time')")
    max_score = fields.FloatField(null=True, description="Максимальный балл (если применимо)")

    class Meta:
        table = "tasks"

    def __str__(self):
        return f"{self.subjects_name} - {self.name}" 