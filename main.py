import time
from PIL import Image, ImageDraw

from app.display import write_to_display, DISPLAY_WIDTH, DISPLAY_HEIGHT
from app import touch
from app.ui.screen import ScreenManager
from app.ui.screens.menu import MainMenuScreen
from app.ui.screens.print_food import PrintFoodScreen
from app.ui.screens.find_recipe import FindRecipeScreen
from app.ui.screens.ask_question import AskQuestionScreen
from app.ui.screens.settings import SettingsScreen
from app.log import setup_logging
log = setup_logging()
log.info("Application starting")

img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)

screen_manager = ScreenManager()
screen_manager.add("menu",         MainMenuScreen(screen_manager))
screen_manager.add("print_food",   PrintFoodScreen(screen_manager))
screen_manager.add("find_recipe",  FindRecipeScreen(screen_manager))
screen_manager.add("ask_question", AskQuestionScreen(screen_manager))
screen_manager.add("settings",     SettingsScreen(screen_manager))
screen_manager.switch_to("menu")
screen_manager.dirty = True

while True:
    tap = touch.poll()
    if tap:
        tx, ty = tap
        screen_manager.active_screen.handle_tap(tx, ty)
    if screen_manager.dirty:
        screen_manager.active_screen.render(draw)
        img.save("/tmp/debug_frame.png")  # inspect this on your Mac
        write_to_display(img)
        screen_manager.dirty = False
    time.sleep(0.01)
