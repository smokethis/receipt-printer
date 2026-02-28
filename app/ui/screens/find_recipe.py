from app.ui.screen import Screen
from app.ui.components import Button, Label
from app.display import DISPLAY_HEIGHT


class FindRecipeScreen(Screen):
    def __init__(self, screen_manager):
        super().__init__()
        self.components.append(Label(20, 20, "Find Recipe", font_size=32))
        self.components.append(
            Button(10, DISPLAY_HEIGHT - 60, 120, 50, "Back",
                   lambda: screen_manager.switch_to("menu"))
        )
