import argparse
import logging

from telegram.ext import ApplicationBuilder, CommandHandler

import env
from handlers import start, conv_handler

TOKEN = env.get('BOT_TOKEN')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        '-v', '--verbose',
        help="Be verbose",
        action="store_const", dest="loglevel", const=logging.INFO,
    )
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    # Initialize the bot
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.run_polling()


if __name__ == "__main__":
    main()
