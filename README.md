# Purgatory — русская локализация

Неофициальная русская локализация **Werewolf: The Apocalypse — Purgatory**
для Steam. Переводятся сюжет, диалоги, описания, улики и связанные с ними
интерфейсные строки. Личные имена, названия навыков и Даров сохраняются как в
английском оригинале.

Локализация использует BepInEx 5 и при запуске заменяет основной скомпилированный
Ink-сценарий `wod02`. Файлы игры не патчатся и не перезаписываются.

## Установка

Актуальная beta-версия: [v0.1.4](https://github.com/Hramgithub/Purgatory_ru/releases/tag/v0.1.4).

1. Скачайте архив релиза `Purgatory-RU-<версия>.zip`.
2. Полностью распакуйте его.
3. Закройте игру и запустите `install.bat`.
4. Если Steam-библиотека не найдена автоматически, выберите папку с
   `Purgatory.exe`.
5. Запустите игру из Steam.

Подробная инструкция и удаление включены в каждый архив. Технические сведения о
проверенной сборке игры находятся в [COMPATIBILITY.md](COMPATIBILITY.md).

Для русского текста используется цельное системное семейство Segoe UI
(при отсутствии — Arial) с обычным, курсивным, жирным и жирным курсивным
начертаниями. Авторские размеры и выделения сохраняются. Файлы шрифтов
Windows не распространяются в архиве и загружаются с компьютера игрока.

## Терминология

Проект придерживается русской терминологии *Werewolf: The Apocalypse 5th
Edition*: Гару, Гайя, Вирм, Вайлд, Ткач, Умбра, Бэйн, септ, каэрн, Ярость,
Сила воли, Харано и Хауглоск. Зафиксированные соответствия перечислены в
[GLOSSARY.md](GLOSSARY.md).

## Как выполнен перевод

Основной Ink-сценарий был разделён на 63 части и переведён через Codex/GPT со
структурированным JSON-выводом. После обратной сборки проверены все 14 067
локализуемых строк, плейсхолдеры, защищённые названия и загрузка результата
самим `Ink.Runtime.Story`. Ollama и локальные модели для итогового перевода не
использовались.

В v0.1.4 выполнен отдельный контекстный проход GPT-редакторов по всему сценарию:
14 067 уникальных строк и 23 146 их вхождений, включая варианты выбора,
продолжения и альтернативные ветки. Изменена 1 651 строка. Повествование Samira
согласовано в женском роде и прошедшем времени; прямая речь, мысли и описания
сохраняют время по смыслу. Исправлены подтверждённые контекстом ошибки имён
в оригинале. Аудит покрытия — [localization/editorial-review.json](localization/editorial-review.json).
Это вычитка сценария, а не полное игровое прохождение всех веток.

## Сборка

```powershell
dotnet build .\src\PurgatoryRu\PurgatoryRu.csproj -c Release
python .\scripts\renderer_commands.py <original-wod02.json> work/ui-command-locations.json
.\scripts\Test-InkUiCommands.ps1 -SourcePath <original-wod02.json> -StoryPath dist/content/wod02.json -LocationsPath work/ui-command-locations.json -ReportPath dist/ui-command-report.json
.\scripts\build_package.ps1
```

Перед упаковкой проверяются все восемь окон создания персонажа через настоящий
Ink runtime: семь полей команды, количество вариантов и внутренние идентификаторы.
Сборка пакета отклоняет отсутствующий отчёт либо отчёт от другого сценария.

Для сборки DLL нужны установленные файлы игры и reference assemblies BepInEx.
Официальный BepInEx 5.4.23.5 x64 загружается отдельно и не берётся из чужих
фанатских переводов.

Перевод хранится в `localization/ru/chunk-*.json`. Для повторной сборки сценария
из собственного извлечённого `wod02` используйте:

```powershell
python .\scripts\assemble_codex_translation.py <original-wod02.json> localization dist/content/wod02.json --report dist/assembly-report.json
```

`localization/index.json` содержит адреса строк, хеши и плейсхолдеры, поэтому
исходный английский сценарий не требуется публиковать в репозитории.

Дополнительные проверки для разработчика выполняются в **PowerShell 7 (`pwsh`)**;
установщику игрока по-прежнему достаточно Windows PowerShell 5.1.

```powershell
python .\scripts\renderer_commands.py <original-wod02.json> work/summary-locations.json --command ui-social-choices
pwsh -NoProfile -File .\scripts\Test-InkChapterSummaries.ps1 -SourcePath <original-wod02.json> -StoryPath dist/content/wod02.json -LocationsPath work/summary-locations.json -ReportPath dist/chapter-summary-report.json
pwsh -NoProfile -File .\scripts\Test-InkRenown.ps1 -SourcePath <original-wod02.json> -StoryPath dist/content/wod02.json -ReportPath dist/renown-report.json
python .\scripts\qa_translation.py <original-wod02.json> dist/content/wod02.json localization --report dist/qa-report.json
python -m unittest discover -s scripts -p "test_*.py"
```

Проверка сводок вызывает все шесть команд через игровой Ink runtime и сверяет
число строк, ключи и количества вариантов вне переводимых полей. Это проверка
формата при начальном состоянии переменных, а не полное прохождение веток.
Статический QA дополнительно проверяет каждое вхождение служебных кавычек
margin, метаданных и неизменяемых команд Ink. Допустимые исправления авторских
тегов перечислены в `localization/render_overrides.json`: они привязаны к хешам
исходных строк, применяются только при сборке и не меняют исходник игры.
Проверка `maxRenown` отдельно воспроизводит равенство всех трёх значений и
попарные ничьи: внутренний литерал `balanced` сохраняется только в сравнении,
а одноимённые видимые подписи локализуются.

Визуально проверено начало игры; полное прохождение всех веток пока не выполнено.
Главное меню, заставки глав и статические элементы HUD остаются на английском.

## Приватность сборки

Release-сборки не включают отладочные символы и личные пути компьютера сборки.
Упаковка проверяет DLL и весь пакет через `scripts/verify_release_privacy.py`;
обнаружение пути профиля пользователя, файла символов или приватного ключа
останавливает сборку. Эта проверка дополняет, но не заменяет сканер секретов.
Архивы v0.1.0–v0.1.4 очищены повторной сборкой; аудит и новые SHA-256 —
в [RELEASE_PRIVACY_AUDIT.json](RELEASE_PRIVACY_AUDIT.json).

## Правовой статус

Это неофициальный некоммерческий фанатский проект. Права на игру, сюжет, сеттинг
World of Darkness и Werewolf: The Apocalypse принадлежат их правообладателям.
В репозитории не публикуются исходные игровые ресурсы; релиз содержит только
локализацию, загрузчик и необходимый runtime BepInEx по лицензии MIT.
