# client/voice_client/finance_news_service.py
import requests
import json
import time
from .tts_stt import speak, listen_input
from .utils import translate_text_if_needed # Из utils
from .config import PUBLIC_ALPHA_VANTAGE_API_KEY, PUBLIC_ALPHA_VANTAGE_URL

# Список известных тем, которые AlphaVantage может понимать (можно расширить)
# Источник: https://www.alphavantage.co/documentation/#news-sentiment (параметр topics)
KNOWN_FINANCIAL_TOPICS = [
    "blockchain", "earnings", "ipo", "mergers_and_acquisitions", 
    "financial_markets", "economy_fiscal", "economy_monetary", "economy_macro", 
    "energy_transportation", "finance", "life_sciences", "manufacturing", 
    "real_estate", "retail_wholesale", "technology",
    # Добавим русские аналоги для распознавания пользовательского ввода
    "блокчейн", "прибыль", "отчетность", "айпио", "слияния", "поглощения",
    "финансовые рынки", "экономика", "макроэкономика", "энергетика", "транспорт",
    "финансы", "биотехнологии", "медицина", "производство", "недвижимость",
    "торговля", "технологии", "нефть", "газ", "металлы", "инфляция", "криптовалюта"
]

# Маппинг русских тем на английские для API
TOPIC_TRANSLATION_MAP = {
    "блокчейн": "blockchain",
    "прибыль": "earnings",
    "отчетность": "earnings",
    "айпио": "ipo",
    "слияния": "mergers_and_acquisitions",
    "поглощения": "mergers_and_acquisitions",
    "финансовые рынки": "financial_markets",
    "экономика": "economy_macro", # Общее
    "макроэкономика": "economy_macro",
    "энергетика": "energy_transportation",
    "транспорт": "energy_transportation",
    "финансы": "finance",
    "биотехнологии": "life_sciences",
    "медицина": "life_sciences",
    "производство": "manufacturing",
    "недвижимость": "real_estate",
    "торговля": "retail_wholesale",
    "технологии": "technology",
    "нефть": "energy_transportation", # AlphaVantage может связать с этим
    "газ": "energy_transportation",
    "металлы": "manufacturing", # Или более специфичную, если есть
    "инфляция": "economy_fiscal", # Или economy_monetary
    "криптовалюта": "blockchain" # Или technology
}


def get_financial_news_from_alphavantage(user_profile_obj: dict | None): # user_profile может быть None
    speak("Финансовый анализ от AlphaVantage. О какой компании (по тикеру, например, 'AAPL' для Apple) или финансовой теме (например, 'ipo', 'блокчейн', 'нефть') вы бы хотели узнать?")
    speak("Если ничего не укажете, я попробую показать общие данные, если они доступны.")

    query_input = listen_input(timeout=12, phrase_time_limit=20)

    params_av = {
        "function": "NEWS_SENTIMENT",
        "apikey": PUBLIC_ALPHA_VANTAGE_API_KEY,
        "limit": "5", 
        "sort": "LATEST"
    }
    request_description_for_speech = "общие финансовые новости"

    if query_input and query_input.strip():
        query_lower = query_input.strip().lower() # Сразу убираем лишние пробелы и приводим к нижнему регистру
        
        potential_tickers = []
        final_topics_for_api = [] # Темы, которые пойдут в API (уже переведенные на англ, если надо)

        # 1. Сначала проверяем, не является ли весь ввод известной темой
        if query_lower in KNOWN_FINANCIAL_TOPICS:
            api_topic = TOPIC_TRANSLATION_MAP.get(query_lower, query_lower) # Переводим тему, если есть в мапе
            final_topics_for_api.append(api_topic)
        else:
            # 2. Если не одна известная тема, разбираем на части
            parts = [p.strip() for p in query_lower.replace(",", " ").split() if p.strip()]
            temp_potential_topics_user_input = []

            for part in parts:
                # Эвристика для тикеров: 1-5 БУКВ (могут быть цифры в некоторых тикерах, но API AlphaVantage для NEWS_SENTIMENT хочет только буквы)
                # и приводим к верхнему регистру, так как API AlphaVantage их так ожидает.
                if part.isalpha() and 1 <= len(part) <= 5:
                    potential_tickers.append(part.upper())
                else:
                    # Если это не тикер, считаем это частью возможной темы
                    temp_potential_topics_user_input.append(part)
            
            # Если после разбора на тикеры остались слова, пробуем их как темы
            if temp_potential_topics_user_input:
                # Сначала пробуем всю оставшуюся фразу как тему
                full_remaining_phrase_as_topic = " ".join(temp_potential_topics_user_input)
                if full_remaining_phrase_as_topic in KNOWN_FINANCIAL_TOPICS:
                    api_topic = TOPIC_TRANSLATION_MAP.get(full_remaining_phrase_as_topic, full_remaining_phrase_as_topic)
                    final_topics_for_api.append(api_topic)
                else: # Если вся фраза не тема, пробуем каждое слово из оставшихся как тему
                    for topic_word in temp_potential_topics_user_input:
                        if topic_word in KNOWN_FINANCIAL_TOPICS:
                            api_topic = TOPIC_TRANSLATION_MAP.get(topic_word, topic_word)
                            if api_topic not in final_topics_for_api: # Избегаем дубликатов тем
                                final_topics_for_api.append(api_topic)
        
        # Формируем параметры запроса и описание
        if potential_tickers:
            params_av["tickers"] = ",".join(list(set(potential_tickers)))
            request_description_for_speech = f"новости по тикерам: {params_av['tickers']}"
            if final_topics_for_api:
                params_av["topics"] = ",".join(list(set(final_topics_for_api)))
                request_description_for_speech += f" и темам: {params_av['topics']}"
        elif final_topics_for_api:
            params_av["topics"] = ",".join(list(set(final_topics_for_api)))
            request_description_for_speech = f"новости по темам: {params_av['topics']}"
        else: # Если ничего не распознали ни как тикер, ни как тему
            speak(f"Не удалось определить тикеры или известные темы из вашего запроса '{query_input}'. Попробую получить общие новости.")
            # request_description_for_speech остается "общие финансовые новости"
    else:
        speak("Запрос не указан, попробую получить общие финансовые новости.")

    speak(f"Запрашиваю {request_description_for_speech} от AlphaVantage...")

    try:
        response = requests.get(PUBLIC_ALPHA_VANTAGE_URL, params=params_av, timeout=20)
        response.raise_for_status()
        data = response.json()

        # print(f"[FinNews Debug] URL Запроса: {response.url}")
        # print(f"[FinNews Debug] Ответ JSON: {json.dumps(data, indent=2, ensure_ascii=False)}")

        feed_items = data.get("feed", [])
        if feed_items:
            speak("Вот некоторые финансовые сводки и анализ настроений:")
            articles_spoken_count = 0
            max_articles_to_speak = 3 # Можно увеличить, если новости короткие

            for item_idx, item in enumerate(feed_items):
                if articles_spoken_count >= max_articles_to_speak:
                    break

                title = item.get("title", "Без заголовка")
                summary = item.get("summary", "Краткое содержание отсутствует.")
                source = item.get("source", "Неизвестный источник")
                
                # Перевод на русский, если необходимо
                translated_title = translate_text_if_needed(title, target_language="ru")
                translated_summary = translate_text_if_needed(summary, target_language="ru")
                translated_source = translate_text_if_needed(source, target_language="ru")

                speak_text_parts = [f"Новость от {translated_source}: {translated_title}."]

                # Анализ настроений по тикерам
                ticker_sentiments_texts = []
                if "ticker_sentiment" in item and isinstance(item["ticker_sentiment"], list):
                    for ts in item["ticker_sentiment"]:
                        ticker = ts.get("ticker")
                        relevance_score_str = ts.get("relevance_score", "0.0")
                        sentiment_label = ts.get("ticker_sentiment_label", "Neutral") # API возвращает на английском
                        
                        try: relevance_float = float(relevance_score_str)
                        except ValueError: relevance_float = 0.0

                        if ticker and sentiment_label and relevance_float > 0.15: # Порог релевантности
                            # Переводим метку настроения
                            translated_sentiment_label = translate_text_if_needed(sentiment_label.replace("_", " ").capitalize(), target_language="ru")
                            ticker_sentiments_texts.append(f"Для тикера {ticker} настроение: {translated_sentiment_label}.")
                
                if ticker_sentiments_texts:
                    speak_text_parts.append(" ".join(ticker_sentiments_texts))
                
                if translated_summary and \
                   translated_summary.lower().strip() != "краткое содержание отсутствует." and \
                   translated_summary.lower().strip() != translated_title.lower().strip() and \
                   len(translated_summary) < 350: # Ограничение длины summary
                     speak_text_parts.append(f"Кратко: {translated_summary}")

                speak_text_final = " ".join(speak_text_parts)
                if len(speak_text_final) > 700: # Обрезаем очень длинные сообщения
                    speak_text_final = speak_text_final[:697] + "..."

                speak(speak_text_final)
                articles_spoken_count += 1
                if articles_spoken_count < len(feed_items) and articles_spoken_count < max_articles_to_speak:
                    time.sleep(1.2)

            if articles_spoken_count == 0 and feed_items:
                speak("Не найдено достаточно релевантных новостей по вашему запросу с доступным содержанием.")
            elif not feed_items and not ("Information" in data or "Note" in data):
                 speak("По вашему запросу не найдено новостей.")

        elif "Information" in data or "Note" in data:
            api_message = data.get('Information', data.get('Note', 'Нет дополнительной информации от API.'))
            # Сообщения от API обычно на английском, их тоже можно перевести
            translated_api_message = translate_text_if_needed(api_message, target_language="ru")
            speak(f"Сообщение от Alpha Vantage: {translated_api_message}")
            print(f"[FinNews AlphaVantage Info] Original: {api_message} | Translated: {translated_api_message}")
        else:
            speak("Не удалось получить финансовые данные или новости. Возможно, API вернул неожиданный ответ или ваш запрос не дал результатов.")
            print(f"[FinNews AlphaVantage] Неожиданный ответ или нет данных. Ответ API: {json.dumps(data, indent=2, ensure_ascii=False)}")

    except requests.exceptions.Timeout:
        speak("Сервер финансовых данных Alpha Vantage не ответил вовремя. Попробуйте позже.")
    except requests.exceptions.HTTPError as http_err:
        error_text = http_err.response.text[:300] if http_err.response else "Нет деталей ответа"
        speak(f"Ошибка при запросе к Alpha Vantage: Код {http_err.response.status_code if http_err.response else 'N/A'}.")
        print(f"[FinNews AlphaVantage HTTP Ошибка] {http_err.response.status_code if http_err.response else 'N/A'} - {error_text}")
        if http_err.response and "Invalid API call" in http_err.response.text:
             speak("Возможно, ваш запрос содержит некорректные тикеры или темы. Пожалуйста, проверьте документацию AlphaVantage.")
    except requests.exceptions.RequestException as e_req:
        speak(f"Ошибка сети при запросе финансовых данных.")
        print(f"[FinNews AlphaVantage Ошибка Запроса] {e_req}")
    except json.JSONDecodeError:
        response_text_snippet = response.text[:300] if 'response' in locals() and hasattr(response, 'text') else 'Нет ответа или ответ не текстовый'
        speak("Получен некорректный ответ от сервера финансовых данных. Попробуйте позже.")
        print(f"[FinNews AlphaVantage Ошибка Декодирования JSON] Ответ сервера: {response_text_snippet}")
    except Exception as e_general:
        speak("Произошла непредвиденная ошибка при получении финансовых данных.")
        print(f"[FinNews AlphaVantage Общая Ошибка] {type(e_general).__name__}: {e_general}")
        import traceback
        traceback.print_exc()