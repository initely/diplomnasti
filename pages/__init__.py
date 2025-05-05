from reflex import rx
from .components.task_page import task_page

app = rx.App()
app.add_page(task_page, route="/task") 