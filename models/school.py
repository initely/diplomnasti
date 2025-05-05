# models/school.py

from tortoise import fields, models

class School(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255, description="Полное название школы")
    
    # Связи "многие ко многим": хранение списков пользователей по ролям.
    # Обратите внимание, что эти связи не заменяют вычисляемые значения, их можно
    # использовать для явного задания связей, если это требуется.
    psychologists = fields.ManyToManyField(
        "models.User",
        related_name="psychologies_in_school",
        description="Психологи, работающие в школе",
        blank=True
    )
    children = fields.ManyToManyField(
        "models.User",
        related_name="child_in_school",
        description="Дети, обучающиеся в школе",
        blank=True
    )
    parents = fields.ManyToManyField(
        "models.User",
        related_name="parents_in_school",
        description="Родители детей, обучающихся в школе",
        blank=True
    )
    
    class Meta:
        table = "school"
        
    def __str__(self):
        return self.name
