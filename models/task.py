from tortoise import fields, models

class Task(models.Model):
    id = fields.IntField(pk=True)
    description = fields.CharField(max_length=255) #Описание задания
    subjects_name = fields.CharField(max_length=255)
    local_id = fields.IntField()  # Локальный номер задания (1-5)
    type = fields.CharField(max_length=50)
    max_score = fields.FloatField()

    class Meta:
        table = "tasks"

    @classmethod
    async def get_task_by_subject_and_local_id(cls, subjects_name: str, local_id: int):
        return await cls.filter(subjects_name=subjects_name, local_id=local_id).first()

    def __str__(self):
        return f"{self.subjects_name} - {self.name}" 