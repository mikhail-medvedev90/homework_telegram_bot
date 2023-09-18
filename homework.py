import logging
import os
import time
from typing import Never, NoReturn

import requests
import telegram

from dotenv import load_dotenv

from exceptions import TokenNotFound, WrongResponseStatusCode


load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO)
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENDPOINT = os.getenv('ENDPOINT')

RETRY_PERIOD = 600
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens() -> None | NoReturn:
    """Check is needed variables is not empty, raise exception otherwise."""
    raise_message = ''
    if not PRACTICUM_TOKEN:
        raise_message = 'PRACTICUM_TOKEN not found'
    if not TELEGRAM_TOKEN:
        raise_message = 'TELEGRAM_TOKEN not found'
    if not TELEGRAM_CHAT_ID:
        raise_message = 'TELEGRAM_CHAT_ID not found'
    if raise_message:
        logging.critical(raise_message)
        raise TokenNotFound(raise_message)
    else:
        logging.info('All tokens upload')


def send_message(bot: telegram.Bot, message: str) -> None:
    """
    Send message to Telegram chat via telegram.Bot instance.
    :param: bot - bot object to send message.
    :param: message - text to send.
    """
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug('Message sent successfully')


def get_api_answer(timestamp: int) -> dict:
    """
    Function sends GET request to Yandex Practicum API.
    And waiting until response.
    Return dict if response.status_code is 200, empty dict otherwise.
    :param: timestamp - required parameter for get request.
    :return: list of homeworks.
    """
    try:
        response: requests.Response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except Exception as error:
        logging.error(f'Error happens while sending the request. '
                      f'It says: {error}')
        return {}
    else:
        if response.status_code == 200:
            logging.info('Response answer is OK')
            return response.json()
        else:
            error_msg = (f'Endpoint is not available. '
                         f'Status code is {response.status_code}')
            logging.error(error_msg)
            raise WrongResponseStatusCode(error_msg)


def check_response(response: dict) -> list[dict] | NoReturn:
    """
    Check keys (`homeworks`, `current_date`) in response.
    Return `homeworks` key`s value, raise ResponseKeyNotFound otherwise.
    :param: response - dict with two keys or fewer.
    :return: list homeworks.
    """
    if (isinstance(response, dict)
            and 'homeworks' in response
            and 'current_date' in response):
        logging.debug('Both keys are in response')
        if isinstance(response['homeworks'], list):
            return response['homeworks']
        raise TypeError('Value of homeworks key is not list instance')
    else:
        msg = 'There are no keys in API response'
        logging.error(msg)
        raise TypeError(msg)


def parse_status(homework: dict) -> str:
    """
    Extract status from homework data.
    :param: homework - dict with all homework`s data.
    :return: str with verdict from HOMEWORK_VERDICTS
    prepared to send in telegram.
    """
    try:
        homework_name = homework['homework_name']
        status = homework['status']
    except KeyError:
        raise KeyError('Key `homework_name` is not found')
    if status not in HOMEWORK_VERDICTS.keys():
        raise KeyError(
            f'Status: {status} is not in {HOMEWORK_VERDICTS.keys()}'
        )
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{HOMEWORK_VERDICTS[status]}')


def main() -> Never:
    """
    Main logic of program.
    1. Send API request;
    2. Check response;
    3. Get updated homework status and send it in Telegram;
    4. Wait some time and go ahead to point 1.
    """
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        timestamp = int(time.time())
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
            logging.info(
                f'Got {len(homeworks)} homeworks. '
                f'Sleep {RETRY_PERIOD} seconds.'
            )

        except Exception as error:
            message = f'Error occurred while loop working: {error}'
            logging.error(message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
