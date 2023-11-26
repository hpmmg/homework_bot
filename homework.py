import logging
import sys
import time
from sys import stdout
from http import HTTPStatus

import requests
import telegram

from exceptions import (
    EnvVariablesNotAvailable,
    UnavailableApi,
    UnknownHomeworkStatus,
    WrongAnswerFormat
)

from config import (
    PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, RETRY_TIME, ENDPOINT,
    HEADERS, HOMEWORK_STATUSES
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Функция для отправки сообщения ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Бот отправил сообщение "{message}"')
    except telegram.error.TelegramError as error:
        logger.error(f'Ошибка {error} при отправке сообщения в телеграм!')


def get_api_answer(current_timestamp):
    """Функция для запроса ресурса с API Практикума."""
    try:
        timestamp = current_timestamp or int(time.time())
        params = {'from_date': timestamp}
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code == HTTPStatus.OK.value:
            logger.info(f'Получен ответ от API {response.json()}')
            return response.json()
        else:
            logger.error('Сбой при запросе к эндпоинту!')
            raise UnavailableApi('Сбой при запросе к API!')
    except Exception as error:
        logger.error('Сбой при запросе к эндпоинту!')
        raise UnavailableApi(f'Сбой при запросе к API! {error}')


def check_response(response):
    """Функция для проверки формата ответа от API Практикума."""
    if isinstance(response, dict) and isinstance(response['homeworks'], list):
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
    except KeyError as error:
        logger.error(f'Неожиданный статус работы! {error}')
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
                sys.exit('Недоступны переменные окружения!')

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

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
