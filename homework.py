import os

import logging

from sys import stdout

import time

import telegram

import requests

import dotenv

from exceptions import (EnvVariablesNotAvailable, UnavailableApi, 
                        UnknownHomeworkStatus, WrongAnswerFormat)

dotenv.load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция для отправки сообщения ботом."""
    try:
        sent_message = bot.send_message(TELEGRAM_CHAT_ID, message)
        if sent_message['text'] == message:
            logger.info(f'Бот отправил сообщение "{message}"')
        else:
            logger.error('Ошибка при отправке сообщения в телеграм!')
    except telegram.error.TelegramError:
        logger.error('Ошибка при отправке сообщения в телеграм!')


def get_api_answer(current_timestamp):
    """Функция для запроса ресурса с API Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    response = requests.get(
        url=ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if response.status_code == requests.codes.ok:
        logger.info(f'Получен ответ от API {response.json()}')
        return response.json()
    else:
        logger.error('Сбой при запросе к эндпоинту!')
        raise UnavailableApi('Сбой при запросе к API')


def check_response(response):
    """Функция для проверки формата ответа от API Практикума."""
    if (('homeworks' and 'current_date') in response
       and isinstance(response['homeworks'], list)):
        logger.info('Формат ответа соответствует ожидаемому')
        return response['homeworks']
    logger.error('Формат ответа НЕ соответствует ожидаемому')
    raise WrongAnswerFormat


def parse_status(homework):
    """Функция для парсинга статуса ДЗ."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        logger.error('Неожиданный статус работы')
        raise UnknownHomeworkStatus


def check_tokens():
    """Функция для проверки доступности переменных окружения."""
    return all([
        TELEGRAM_TOKEN,
        PRACTICUM_TOKEN,
        TELEGRAM_CHAT_ID
    ])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    api_error_count = 0

    while True:
        try:
            if check_tokens():
                logger.info('Все переменные окружения доступны')
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                if len(homeworks) > 0:
                    for homework in homeworks:
                        message = parse_status(homework)
                        send_message(bot, message)
                else:
                    logger.debug('Нет изменений в статусах работ')
                current_timestamp = response['current_date']
            else:
                logger.critical('Недоступны переменные окружения!')
                raise EnvVariablesNotAvailable('EnvVarsNotAvail')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if (not isinstance(error, EnvVariablesNotAvailable)
               and not isinstance(error, telegram.error.TelegramError)):
                if isinstance(error, UnavailableApi):
                    if api_error_count == 0:
                        send_message(bot, message)
                        api_error_count += 1
                else:
                    send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            ...


if __name__ == '__main__':
    main()
