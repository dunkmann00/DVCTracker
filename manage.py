from flask_script import Manager

from main import app
from main import update_specials

manager = Manager(app)

@manager.command
def dvcupdate():
    update_specials()

if __name__ == "__main__":
    manager.run()
