from tortoise import fields, models

class Answer(models.Model):
    id = fields.IntField(pk=True)
    task = fields.ForeignKeyField("models.Task", related_name="answers", null=True, on_delete=fields.SET_NULL)
    answer = fields.TextField()  # Храним ответ как текст

    class Meta:
        table = "answer"
