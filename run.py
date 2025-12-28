import os
from app import create_app, db
from app.models import User, List, Item, Claim

# Determine environment
env = os.environ.get('FLASK_ENV', 'production')
app = create_app(env)


# Shell context for flask shell command
@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'List': List,
        'Item': Item,
        'Claim': Claim
    }


if __name__ == '__main__':
    app.run()
