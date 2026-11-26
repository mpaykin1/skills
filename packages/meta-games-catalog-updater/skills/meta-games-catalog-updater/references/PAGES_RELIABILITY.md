# Pages reliability gate — обязательный протокол публикации

Production: `mpaykin1/meta6`, `main`, `.github/workflows/meta6-pages.yml`, имя `Publish complete META6 site`. Не использовать исторический `pages/pages-build-deployment`. Не менять Settings/Pages, домен, веточную защиту, guard или чужие игры ради обхода ошибки. Проверенный выпуск: https://github.com/mpaykin1/meta6/commit/696100335d24e1269be3df3793aea6bbca1c6fba ; https://github.com/mpaykin1/meta6/actions/runs/45643329684 . Читать актуальный workflow, не переписывать последующие улучшения старым шаблоном.

## Автоматическая диагностика

Через подключённый GitHub: `fetch_commit` для main, затем `fetch` с точным URL `https://api.github.com/repos/mpaykin1/meta6/actions/runs` (проверен; не добавлять query string, если connector его отвергает). Разобрать JSON workflow_runs, выбрать name == Publish complete META6 site, head_branch == main, head_sha актуального выпуска; учитывать push и workflow_dispatch. При необходимости читать разрешённые страницы. `fetch_commit_workflow_runs` фильтрует PR и может вернуть пустой список даже при успешном push: пустой ответ не означает отсутствия запуска. Не считать старый success подтверждением нового SHA.

Для фактического run_id использовать fetch_workflow_run_jobs, fetch_workflow_run_artifacts, fetch_workflow_job_steps и fetch_workflow_job_logs с реальным job_id упавшего задания. Проверить имя, ID, размер, expired, run ID и attempt артефакта. Не подставлять номер запуска вместо run ID. Если данные доступны, не просить пользователя присылать скриншоты или нажимать кнопки. Для ссылки использовать html_url из результата. При активном запуске проверять в пределах текущего сеанса; не обещать будущую работу.

## Инварианты workflow, подтверждённые запуском #325

- push на main и workflow_dispatch; публикация только refs/heads/main; concurrency для единственного действующего сайта. Не ослаблять ограничения.
- build собирает полный сайт в _site, сохраняет прежние игры, .nojekyll, существующие проверки обязательных путей, каталог и sitemap. actions/configure-pages и actions/upload-pages-artifact (проверенные версии v5/v4), id: upload.
- Имя архива github-pages-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT} формируется в build и передаётся как output artifact_name; при наличии artifact_id тоже передать из upload. Для повтора только deploy использовать outputs успешного build, не вычислять имя по новому attempt.
- deploy: отдельное задание, needs: build, environment: github-pages, permissions contents: read, actions: read, pages: write, id-token: write (или эквивалент с меньшими правами). Checkout той же ревизии для live-проверки.
- Перед deploy дождаться видимости архива через gh api GET repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts с точным именем и при наличии ID из outputs; ровно один неистёкший архив, размер > 0. Максимум 30 попыток × 5 сек; если недоступен, завершить с явной ошибкой. Не обходить несовпадение имён.
- actions/deploy-pages@v4 (либо проверенная совместимая версия), явно передать artifact_name: ${{ needs.build.outputs.artifact_name }}. Retention эталона 7 дней. Не подменять артефакт чужим архивом, не удалять сайты и не увеличивать расходы без разрешения.
- Сохранить Confirm live games, SEO catalog and sitemap revision после реального deploy. Воссоздать _site из того же SHA с теми же исключениями. curl -fsSL с no-cache, ?rev=$GITHUB_SHA, конечными таймаутами, cmp с ожидаемыми файлами. Проверять прежние игры, каталог, sitemap; для новой игры дополнительно 8 локалей, изменённые жанры, обложку и ссылки. CI только EN + sitemap не покрывает остальные локали и изображение.

## Восстановление по типу сбоя

- No artifacts named "github-pages" / Found 0 artifact(s) при зелёном upload: не повторять сломанный workflow. Проверить run, артефакт, name/ID и совместимость версий; применить split build/deploy с ожиданием, если его нет. При временном сбое после исправления проверить логи; максимум один осмысленный retry актуальной ревизии за запуск с новой информацией. Не обещать исключить внешние отказы.
- Не стартовал push: сверить источник Pages, события/фильтры, разрешения и SHA. При доступном авторизованном dispatch запустить main. Не подменять пустым коммитом и не rerun старый SHA. При недоступности dispatch назвать конкретный блокер.
- build красный: исправить точный дефект, не удалять проверки и не сокращать контент ради зелёного статуса.
- deploy зелёный, live verification красный: отличить CDN-задержку, неверный артефакт, неверный URL и потерю файлов; проверить обычный URL и URL с SHA. Не создавать дубль игры и не считать query-параметр исправлением деплоя.
- Всё зелёное для текущего SHA: подтвердить конкретные шаги и содержимое checkout. При доступном HTTP сверить обычную страницу, ревизию, реальные карточки, изображение, ссылки. Если браузер недоступен, дать ссылку на фактический успешный run и назвать границы CI, не требовать ручного запуска.

## Критерий завершения

source_added ≠ pages_deployed ≠ live_verified. Проверить совпадение SHA выпуска с workflow, success build/upload/wait/deploy/live-content. Новая карточка первая и единственная по точному URL во всех 8 локалях, три прямые ссылки Playgama, обложка загружена и декодируется, старые карточки сохранены, релевантные жанры и SEO обновлены. Если часть проверок недоступна, назвать только конкретный блокер, не сообщать полного успеха. Вернуть ссылку каталога без лишних отчётов.
