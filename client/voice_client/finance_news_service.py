# client/voice_client/finance_news_service.py
import requests
import json
import time
from .tts_stt import speak, listen_input
from .utils import translate_text_if_needed # Из utils
from .config import PUBLIC_ALPHA_VANTAGE_API_KEY, PUBLIC_ALPHA_VANTAGE_URL

def get_financial_news_from_alphavantage(user_profile_obj: dict | None): # user_profile может быть None
    speak("Финансовый анализ от AlphaVantage. О какой компании (по тикеру, например, 'AAPL' для Apple) или финансовой теме (например, 'ipo', 'блокчейн', 'нефть') вы бы хотели узнать?")
    speak("Если ничего не укажете, я попробую показать общие данные, если они доступны.")

    # ИСПРАВЛЕНИЕ: Используем правильные имена параметров для listen_input
    query_input = listen_input(timeout_param=12, phrase_time_limit_param=20) # Даем больше времени на размышление

    params_av = {
        "function": "NEWS_SENTIMENT",
        "apikey": PUBLIC_ALPHA_VANTAGE_API_KEY,
        "limit": "5" # Alpha Vantage ожидает строку для limit, хоть и числовую. Увеличил до 5.
        # "sort": "LATEST" # или "RELEVANCE" - зависит от того, что важнее
    }

    request_description_for_speech = "общие данные"

    if query_input:
        potential_tickers = []
        potential_topics = []
        # Пробуем разделить по запятой или пробелу и обработать каждое слово
        parts = [p.strip() for p in query_input.replace(",", " ").split() if p.strip()]

        for part in parts:
            # Простая эвристика для тикеров (обычно 1-5 заглавных букв)
            if part.isupper() and 1 <= len(part) <= 5 and part.isalpha():
                potential_tickers.append(part)
            else: # Остальное считаем темой (может быть и тикер в нижнем регистре)
                potential_topics.append(part.lower()) # AlphaVantage предпочитает темы в lowercase

        if potential_tickers:
            params_av["tickers"] = ",".join(potential_tickers)
            request_description_for_speech = f"данные по тикерам: {', '.join(potential_tickers)}"
        elif potential_topics: # Если тикеров нет, но есть темы
            params_av["topics"] = ",".join(potential_topics)
            request_description_for_speech = f"данные по темам: {', '.join(potential_topics)}"
        else: # Если ввод был, но не удалось классифицировать
            # Если не удалось распознать, не будем добавлять ни tickers, ни topics,
            # чтобы получить общие новости, как и обещали.
            # params_av["tickers"] = query_input.upper() # Убрал эту строку
            # request_description_for_speech = f"данные по запросу: {query_input}" # Оставим "общие данные"
            speak(f"Не удалось точно определить тикеры или темы из '{query_input}'. Попробую получить общие новости.")
    else:
        speak("Запрос не указан, попробую получить общие новости.")


    speak(f"Запрашиваю {request_description_for_speech} от AlphaVantage...")

    try:
        response = requests.get(PUBLIC_ALPHA_VANTAGE_URL, params=params_av, timeout=20)
        response.raise_for_status() # Проверка на HTTP ошибки
        data = response.json()

        # print(f"[FinNews Debug] URL Запроса: {response.url}") # Отладка URL
        # print(f"[FinNews Debug] Ответ JSON: {json.dumps(data, indent=2, ensure_ascii=False)}") # Отладка

        feed_items = data.get("feed", [])
        if feed_items:
            speak("Вот некоторые финансовые сводки и анализ настроений:")
            articles_spoken_count = 0
            max_articles_to_speak = 2 # Ограничиваем количество озвучиваемых новостей

            for item_idx, item in enumerate(feed_items):
                if articles_spoken_count >= max_articles_to_speak:
                    break

                title = item.get("title", "Без заголовка")
                summary = item.get("summary", "Краткое содержание отсутствует.")
                source = item.get("source", "Неизвестный источник")
                time_published_str = item.get("time_published", "") # Пример: "20231027T103000"

                # Попробуем извлечь настроения для каждого тикера, если они есть
                ticker_sentiments_texts = []
                if "ticker_sentiment" in item and isinstance(item["ticker_sentiment"], list):
                    for ts in item["ticker_sentiment"]:
                        ticker = ts.get("ticker")
                        relevance = ts.get("relevance_score")
                        sentiment_label = ts.get("ticker_sentiment_label")
                        # sentiment_score = ts.get("ticker_sentiment_score") # Не озвучиваем числовой скор для краткости
                        if ticker and sentiment_label:
                            # Переводим метку настроения, если нужно
                            translated_sentiment_label = translate_text_if_needed(sentiment_label.replace("_", " ").capitalize())
                            ticker_sentiments_texts.append(f"Для {ticker}: {translated_sentiment_label} (релевантность {relevance}).")


                translated_title = translate_text_if_needed(title)
                translated_summary = translate_text_if_needed(summary)

                # Формируем текст для озвучивания
                speak_text_parts = [f"Новость от {translate_text_if_needed(source)}: {translated_title}."]

                if ticker_sentiments_texts:
                    speak_text_parts.append(" ".join(ticker_sentiments_texts))

                # Добавляем summary, если оно не пустое и не слишком длинное (и не дублирует title)
                if translated_summary and translated_summary.lower() != translated_title.lower() and len(translated_summary) < 250 :
                     speak_text_parts.append(f"Кратко: {translated_summary}")

                speak_text_final = " ".join(speak_text_parts)
                if len(speak_text_final) > 600: # Обрезаем слишком длинные сообщения
                    speak_text_final = speak_text_final[:597] + "..."

                speak(speak_text_final)
                articles_spoken_count += 1
                if articles_spoken_count < len(feed_items) and articles_spoken_count < max_articles_to_speak: # Пауза если будет еще новость
                    time.sleep(1.0)

            if articles_spoken_count == 0: # Если feed_items был, но ничего не озвучили (маловероятно с текущей логикой)
                speak("Не найдено подходящих финансовых данных по вашему запросу с доступным содержанием.")

        elif "Information" in data or "Note" in data:
            api_message = data.get('Information', data.get('Note', 'Нет дополнительной информации от API.'))
            speak(f"Сообщение от Alpha Vantage: {translate_text_if_needed(api_message)}")
            print(f"[FinNews AlphaVantage Info] {api_message}")
        else:
            speak("Не удалось получить финансовые данные или новости по вашему запросу. Возможно, нет новостей для указанных параметров.")
            print(f"[FinNews AlphaVantage] Нет элементов 'feed' и нет 'Information/Note'. Ответ API: {data}")

    except requests.exceptions.Timeout:
        speak("Сервер финансовых данных Alpha Vantage не ответил вовремя. Попробуйте позже.")
    except requests.exceptions.HTTPError as http_err:
        speak(f"Ошибка при запросе к Alpha Vantage: Код {http_err.response.status_code}. Проверьте ваш API ключ и параметры запроса.")
        print(f"[FinNews AlphaVantage HTTP Ошибка] {http_err.response.status_code} - {http_err.response.text[:300]}")
    except requests.exceptions.RequestException as e_req:
        speak(f"Ошибка сети при запросе финансовых данных.") # Не озвучиваем детали ошибки пользователю
        print(f"[FinNews AlphaVantage Ошибка Запроса] {e_req}")
    except json.JSONDecodeError:
        speak("Получен некорректный ответ от сервера финансовых данных. Попробуйте позже.")
        print(f"[FinNews AlphaVantage Ошибка Декодирования JSON] Ответ сервера: {response.text[:300] if 'response' in locals() else 'Нет ответа'}")
    except Exception as e_general:
        speak("Произошла непредвиденная ошибка при получении финансовых данных.")
        print(f"[FinNews AlphaVantage Общая Ошибка] {e_general}")
        import traceback
        traceback.print_exc()