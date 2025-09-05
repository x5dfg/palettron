# MILKBOT PY 3.13.x

## Установка и запуск

### Клонировать:

```
git clone https://github.com/x5dfg/palettron.git
```
>[!WARNING]
>Обязательно убедитесь что вы указали токен для бота в `bot.py` в переменной `API_TOKEN`

### Ручной запуск:
```
pip install -r requirements.txt
python bot.py
```
### Docker запуск:
```
docker build -t mlkimage .
docker run --name milkbot1 --restart unless-stopped mlkimage
```

## Дополнение

В `palettes.json` можно добавлять/изменять палитры.
Описание ключ-значений:
```json
[
  {
    "label": "Lite Milk", // Название палитры которое видно на кнопке
    "fdata": "lite_milk", // короткое название которое используется в callback данных
    "colors": [[142,165,147], [56,111,107], [48,28,30], [26,22,23], [175,50,44], [78,39,61], [173,55,54]] // Сама палитра цветов
  },
  ...
]

```
