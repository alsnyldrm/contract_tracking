import logging

from alembic import command
from alembic.config import Config

from app.core.logging_config import bootstrap_startup_logs, log_event


def main():
    bootstrap_startup_logs()
    try:
        cfg = Config('alembic.ini')
        command.upgrade(cfg, 'head')
        log_event('db', logging.INFO, 'Migration başarıyla tamamlandı', module='migration', action='upgrade_head')
        print('Migration tamamlandı.')
    except Exception as exc:
        log_event('db', logging.ERROR, 'Migration hatası', module='migration', action='upgrade_head', details={'error': str(exc)}, exc_info=exc)
        raise


if __name__ == '__main__':
    main()
