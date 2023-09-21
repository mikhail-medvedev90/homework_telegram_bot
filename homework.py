import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import TokenNotFound, WrongResponseStatusCode


load_dotenv()

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


def check_tokens():
    """Check is needed variables is not empty, raise exception otherwise."""
    source = "PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"
    not_found_tokens = [token for token in source if not globals()[token]]

    if not_found_tokens:
        critical_msg = f"Tokens: {', '.join(not_found_tokens)} not found."
        logging.critical(critical_msg)
        raise TokenNotFound(critical_msg)
    logging.info('All tokens upload')


def send_message(bot: telegram.Bot, message: str):
    """
    Send message to Telegram chat via telegram.Bot instance.
    :param: bot - bot object to send message.
    :param: message - text to send.
    """
    try:
        logging.info(f"Start sending message to telegram: {TELEGRAM_CHAT_ID}")
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Message sent successfully')
    except telegram.TelegramError as error:
        logging.error(
            f'Error happens while sending message to telegram: {error}'
        )


def get_api_answer(timestamp: int):
    """
    Function sends GET request to Yandex Practicum API.
    And waiting until response.
    Return dict if response.status_code is 200, empty dict otherwise.
    :param: timestamp - required parameter for get request.
    :return: list of homeworks.
    """
    try:
        logging.info(
            f'Start sending request to API: {ENDPOINT}, '
            f'headers={HEADERS}, params={{"from_date": {timestamp}}}'
        )
        response: requests.Response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        logging.debug('Response sent is OK')
    except requests.RequestException as error:
        raise ConnectionError(
            'Error happens while sending the request. '
            f'It says: {error}'
        )
    if response.status_code != HTTPStatus.OK:
        raise WrongResponseStatusCode(
            'Endpoint is not available. '
            f'Status code is {response.reason}'
        )
    return response.json()


def check_response(response: dict):
    """
    Check keys (`homeworks`, `current_date`) in response.
    Return `homeworks` key`s value, raise ResponseKeyNotFound otherwise.
    :param: response - dict with two keys or fewer.
    :return: list homeworks.
    """
    logging.info('Start checking the server response')
    if not isinstance(response, dict):
        raise TypeError('Server response is not dict instance')
    if 'homeworks' not in response:
        raise TypeError('There are no key "homeworks" in API response')
    if 'current_date' not in response:
        raise TypeError('There are no key "current_date" in API response')
    logging.debug('Both keys are in response')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Value of homeworks key is not list instance')
    return response['homeworks']


def parse_status(homeworks: dict):
    """
    Extract status from homework data.
    :param: homework - dict with all homework`s data.
    :return: str with verdict from HOMEWORK_VERDICTS
    prepared to send in telegram.
    """
    logging.info('Start checking status is homework')
    if 'homework_name' not in homeworks:
        raise KeyError('Key `homework_name` is not found')
    if 'status' not in homeworks:
        raise KeyError('Key `status` is not found')
    status = homeworks['status']
    homeworks_name = homeworks['homework_name']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Status: {status} is not in {HOMEWORK_VERDICTS}.'
        )
    logging.debug('Status check was successful in response')
    return (f'Изменился статус проверки работы "{homeworks_name}". '
            f'{HOMEWORK_VERDICTS[status]}')


def main():
    """
    Main logic of program.
    1. Send API request;
    2. Check response;
    3. Get updated homework status and send it in Telegram;
    4. Wait some time and go ahead to point 1.
    """
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logging.info(
                    f'Got {len(homeworks)} homeworks. '
                    f'Sleep {RETRY_PERIOD} seconds.'
                )
            else:
                logging.debug('No new statuses in response')
            timestamp = int(time.time())

        except Exception as error:
            message = f'Error occurred while loop working: {error}'
            logging.error(message, exc_info=True)
            if message != old_message:
                send_message(bot, message)
                old_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(lineno)d - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[logging.StreamHandler(stream=sys.stdout)]
    )
    main()
