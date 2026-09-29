"""Browser portal for interactive OIDC, engineering overview and human decisions."""

HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#101d2a">
<title>Инженерная система · БПЛА</title>
<link rel="stylesheet" href="ui.css">
</head>
<body>
<a class="skip" href="#main">К содержимому</a>
<div class="shell">
  <aside class="sidebar" aria-label="Навигация">
    <div class="brand">
<span class="brand-mark" aria-hidden="true">✦</span>
<div>
<strong>ATLAS</strong>
<small>Инженерная система</small>
</div>
</div>
    <div class="sidebar-caption">Рабочее пространство</div>
    <nav>
      <a href="#overview" class="nav-link selected">Обзор</a>
      <a href="#guide" class="nav-link">Как работать</a>
      <a href="#team" class="nav-link">Команда агентов</a>
      <a href="#project" class="nav-link">Структура проекта</a>
      <a href="#assistant" class="nav-link">Помощник Alice</a>
      <a href="#review" class="nav-link">Проверка и L3</a>
    </nav>
    <div class="sidebar-note">
<span class="status-dot">
</span>
<span>Staging · инженерные данные требуют проверки</span>
</div>
  </aside>
  <div class="content">
    <header class="topbar">
<div class="breadcrumb">Рабочее пространство <span> / </span> Обзор</div>
      <div class="auth">
<span id="identity" class="identity">Гостевой просмотр</span>
<button id="login" class="button button-small">Войти через Keycloak</button>
</div>
    </header>
    <main id="main">
      <section id="lifecycle" class="lifecycle panel" aria-labelledby="lifecycle-title">
        <div class="panel-heading">
<div><div class="eyebrow">Путь проекта</div><h2 id="lifecycle-title">Жизненный цикл разработки</h2></div>
<span id="lifecycle-badge" class="badge badge-muted">Проект не выбран</span>
</div>
        <p id="lifecycle-summary" class="muted">Выберите черновик ниже. Здесь будет показано только подтверждённое состояние выбранного проекта.</p>
        <ol class="lifecycle-steps">
<li data-stage="draft"><strong>Замысел</strong><small>Цель и ограничения от человека</small></li>
<li data-stage="requirements"><strong>Требования</strong><small>Предложения и трассировка</small></li>
<li data-stage="architecture"><strong>Архитектура</strong><small>Функции и распределение</small></li>
<li data-stage="implementation"><strong>Реализация</strong><small>ПО и аппаратура</small></li>
<li data-stage="verification"><strong>Верификация</strong><small>Проверки и свидетельства</small></li>
<li data-stage="review"><strong>Проверка</strong><small>Независимый review</small></li>
<li data-stage="baseline"><strong>Baseline</strong><small>Личное решение L3</small></li>
</ol>
        <p class="fine">После изменений цикл повторяется через Change Request. Этапы справа от текущего — схема процесса, а не выполненные действия агентов.</p>
      </section>
      <section id="guide" class="panel guide" aria-labelledby="guide-title">
        <div class="panel-heading">
          <div><div class="eyebrow">Начало работы</div><h2 id="guide-title">Как пользоваться системой</h2></div>
          <span class="badge badge-muted">Текущие возможности</span>
        </div>
        <ol class="guide-steps">
          <li><strong>Войдите через Keycloak.</strong> Ваши черновики и диалоги видны только вашей учётной записи.</li>
          <li><strong>Создайте черновик.</strong> Укажите цель и известные ограничения. Это ваши исходные сведения, ещё не требования и не модель.</li>
          <li><strong>Выберите черновик и обсудите его с Alice.</strong> Она получает исходный текст и часть сохранённого диалога.
            Ниже чата показано, сколько именно реплик передано.</li>
          <li><strong>Соберите форму из диалога.</strong> Alice задаст нужные вопросы; проверьте её предложение и
            подтвердите создание Change Request и первой области с ролью gateway-modify.</li>
          <li><strong>Проверяйте рабочую область, когда она создана.</strong> Загрузите UUID, изучите версии и evidence;
            независимый reviewer записывает review. Только человек с L3 может утвердить baseline.</li>
        </ol>
        <div class="baseline-guide">
          <strong>Что такое baseline и как его менять?</strong>
          <p>Исходный пустой снимок — начальная версия для работы, без утверждения конструкции. Рабочая область содержит
            предлагаемые изменения. Утверждённый baseline фиксирует проверенный состав проекта: Git commit/tag и версии
            внешних систем. Его нельзя редактировать на месте; следующая редакция проходит через новый Change Request,
            рабочую область, проверки и личное решение L3.</p>
          <p>Первая область создаётся без baseline из зафиксированного Git-снимка и Change Request после вашего подтверждения.
            Исходный черновик служит выбранным контекстом; его текст пока не переносится в инженерные артефакты автоматически.</p>
        </div>
        <p class="fine">Подробности: <a href="https://github.com/alaramia122/Multi-agent_aircraft_developer/blob/main/docs/user-guide.md"
          target="_blank" rel="noopener noreferrer">руководство пользователя</a>.</p>
      </section>
      <section id="overview" class="hero" aria-labelledby="hero-title">
        <div>
<div class="eyebrow">Проектирование авионики БПЛА</div>
          <h1 id="hero-title">От идеи до проверяемой архитектуры</h1>
          <p>Начните новый проект с собственной цели и ограничений. Здесь также видны роли команды, данные рабочих областей и путь к решению человека.</p>
          <div class="hero-actions">
<a class="button button-primary" href="#project">Открыть проект <span aria-hidden="true">↗</span>
</a>
<a class="text-link" href="#assistant">Спросить помощника</a>
</div>
        </div>
        <div class="hero-art" aria-hidden="true">
<div class="orbit orbit-a">
</div>
<div class="orbit orbit-b">
</div>
<div class="plane">✈</div>
<span class="orbit-label one">ТРЕБОВАНИЯ</span>
<span class="orbit-label two">АРХИТЕКТУРА</span>
<span class="orbit-label three">ПРОВЕРКА</span>
</div>
      </section>
      <div id="status" class="notice" role="status" aria-live="polite">Войдите, чтобы открыть инженерные данные и диалог с помощником.</div>
      <section class="metrics" aria-label="Сводка">
        <div class="metric">
<span>Рабочая область</span>
<strong id="metric-workspace">Не выбрана</strong>
<small id="metric-workspace-detail">Введите UUID ниже</small>
</div>
        <div class="metric">
<span>Элементы / связи</span>
<strong id="metric-graph">— / —</strong>
<small>Только изменения области</small>
</div>
        <div class="metric">
<span>Активные агенты</span>
<strong id="metric-agents">Неизвестно</strong>
<small id="metric-telemetry">Телеметрия не подключена</small>
</div>
        <div class="metric">
<span>Готовность к L3</span>
<strong id="metric-review">Не проверена</strong>
<small>Решение принимает человек</small>
</div>
      </section>
      <div class="columns">
        <section id="team" class="panel" aria-labelledby="team-title">
          <div class="panel-heading">
<div>
<div class="eyebrow">01 · Система</div>
<h2 id="team-title">Команда агентов</h2>
</div>
<span id="team-badge" class="badge badge-muted">Нет телеметрии</span>
</div>
          <p class="muted">Роли показывают запланированную структуру. Статус и задача обновляются только из наблюдаемого выполнения; отсутствие телеметрии не означает простой.</p>
          <div id="agent-list" class="agent-list">
<p class="empty">Загружаем роли…</p>
</div>
          <div class="callout">
<strong>Как работает цепочка?</strong>
<span>Требования → архитектура → безопасность и ПО → верификация → контроль конфигурации. Главный инженер координирует предложения; L3 остаётся за человеком.</span>
</div>
        </section>
        <section id="project" class="panel" aria-labelledby="project-title">
          <div class="panel-heading">
<div>
<div class="eyebrow">02 · Данные</div>
<h2 id="project-title">Структура проекта</h2>
</div>
</div>
          <p class="muted">Черновик проекта хранит введённые вами исходные данные. Он не создаёт требований, модели или baseline автоматически.</p>
          <details class="project-start">
            <summary>Три демонстрационные цепочки проектов</summary>
            <p class="muted">Примеры показывают полные типизированные связи по профилям. Их документы, испытания и baseline не создавались в рабочих системах.</p>
            <div id="example-list" class="draft-list">Загружаем примеры…</div>
          </details>
          <div class="project-start">
<h3>Новый проект с нуля</h3>
<label for="new-name">Название</label>
<input id="new-name" maxlength="255" placeholder="Например: демонстратор авионики">
<label for="new-goal">Цель и назначение</label>
<textarea id="new-goal" maxlength="10000" rows="3" placeholder="Что должен делать проект и для кого? Это исходный текст автора, не готовое требование."></textarea>
<label for="new-constraints">Исходные ограничения (если известны)</label>
<textarea id="new-constraints" maxlength="10000" rows="2" placeholder="Укажите известные ограничения или оставьте пустым."></textarea>
<button id="create-project" class="button button-primary">Создать черновик</button>
<div id="project-feedback" class="project-feedback" role="status" aria-live="polite"></div>
<small>После сохранения показываются автор, версия и хэш исходного текста. Агентная обработка пока не запускается.</small>
<div id="draft-list" class="draft-list">Войдите, чтобы увидеть ваши черновики.</div>
</div>
          <div class="project-start">
<h3>Первая рабочая область</h3>
<p class="muted">Выберите свой черновик выше. Нужна роль gateway-modify, открытый Change Request без baseline и подготовленный Git-репозиторий.</p>
<label for="initial-cr">UUID Change Request</label>
<input id="initial-cr" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="off" spellcheck="false">
<label for="initial-repo">Git-репозиторий</label>
<input id="initial-repo" placeholder="Путь или адрес репозитория, доступный Gateway" autocomplete="off" spellcheck="false">
<label for="initial-ref">Git ref</label>
<input id="initial-ref" value="HEAD" autocomplete="off" spellcheck="false">
<button id="create-workspace" class="button button-primary">Создать первую область</button>
<div id="workspace-feedback" class="project-feedback" role="status" aria-live="polite"></div>
</div>
          <h3>Инженерная рабочая область</h3>
          <p class="muted">Фактические элементы и связи выбранной области — её изменения, а не вся утверждённая модель.</p>
          <div class="workspace-form">
<label for="workspace">UUID рабочей области</label>
<div class="input-row">
<input id="workspace" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" autocomplete="off" spellcheck="false">
<button id="load" class="button button-primary">Загрузить</button>
</div>
<small>UUID можно получить из Change Request или журнала Gateway.</small>
</div>
          <div id="project-meta" class="project-meta">
<span>Пакет ещё не загружен</span>
</div>
          <div id="project-graph" class="graph-empty">Здесь появится структура после загрузки пакета.</div>
          <details class="raw">
<summary>Исходный пакет, версии и хэши</summary>
<pre id="package">Нет данных</pre>
</details>
        </section>
      </div>
      <div class="columns lower">
        <section id="assistant" class="panel" aria-labelledby="chat-title">
          <div class="panel-heading">
<div>
<div class="eyebrow">03 · Диалог</div>
<h2 id="chat-title">Помощник Alice</h2>
</div>
<span id="alice-state" class="badge">Ожидает запроса</span>
</div>
          <p class="muted">Поможет разобраться в данных и следующем шаге. Диалог сохраняется для выбранного проекта
            и восстановится после обновления страницы. Ответ не является проверкой или утверждением baseline.</p>
          <div id="chat-project" class="chat-project">Черновик проекта не выбран. Выберите его в разделе «Структура проекта», чтобы обсудить исходную цель.</div>
          <div id="memory-state" class="memory-state" role="status" aria-live="polite">Контекст Alice: выберите проект.</div>
          <details class="memory-detail"><summary>Какие прошлые сообщения получает Alice?</summary>
            <p id="memory-detail">Полный журнал сохраняется для выбранного проекта. В один запрос модели передаются исходный
              черновик и не более 24 последних реплик в пределах 24 000 символов. Число переданных реплик показано выше;
              старые записи остаются в журнале, но не обязательно попадают в очередной запрос.</p>
          </details>
          <div id="conversation" class="conversation" role="log" aria-live="polite">
<div class="welcome">
<span class="avatar">✦</span>
<p>Здравствуйте! Спросите о процессе проектирования или включите пакет области, чтобы обсудить его содержимое.</p>
</div>
</div>
          <label for="message" class="sr-only">Сообщение</label>
<textarea id="message" rows="3" maxlength="2000" placeholder="Например: какие доказательства нужны перед проверкой?">
</textarea>
          <div class="chat-footer">
<label class="check">
<input id="include-workspace" type="checkbox"> Передать выбранный пакет Alice</label>
<button id="send" class="button button-primary">Отправить <span aria-hidden="true">↗</span>
</button>
</div>
          <div class="project-start">
<h3>Начать проект по итогам диалога</h3>
<p class="muted">Alice задаст недостающие вопросы и предложит форму. Запись в OpenProject и создание области
произойдут только после вашего подтверждения с ролью gateway-modify.</p>
<button id="prepare-start" class="button">Собрать форму из диалога</button>
<div id="start-feedback" class="project-feedback" role="status" aria-live="polite"></div>
<div id="start-form" hidden>
<label for="start-title">Название Change Request</label>
<input id="start-title" maxlength="255">
<label for="start-description">Описание и исходная цель</label>
<textarea id="start-description" rows="5" maxlength="10000"></textarea>
<pre id="start-sources" class="project-meta"></pre>
<label class="check"><input id="start-confirmed" type="checkbox"> Я проверил форму и подтверждаю создание Change Request и первой рабочей области</label>
<button id="confirm-start" class="button button-primary">Подтвердить и создать</button>
</div>
</div>
        </section>
        <section id="review" class="panel" aria-labelledby="review-title">
          <div class="panel-heading">
<div>
<div class="eyebrow">04 · Решение</div>
<h2 id="review-title">Независимая проверка</h2>
</div>
<span class="badge badge-warn">Только человек</span>
</div>
          <p class="muted">Сначала откройте пакет и сверьте исходные артефакты, версии, validation и reconciliation.
          Независимый reviewer и утверждающий должны быть разными людьми.</p>
          <div class="step">
<span>1</span>
<div>
<strong>Проверьте пакет</strong>
<small>Используйте раздел «Структура проекта» и исходный JSON.</small>
</div>
</div>
          <div class="step">
<span>2</span>
<div>
<strong>Запишите review</strong>
<small>Укажите причину и URI проверенного свидетельства.</small>
</div>
</div>
          <div class="step">
<span>3</span>
<div>
<strong>Примите L3-решение</strong>
<small>Gateway проверит актуальность evidence и ваши права.</small>
</div>
</div>
          <div class="form-grid">
<label>Причина review <input id="reason" placeholder="Что именно проверено">
</label>
<label>URI свидетельства <input id="evidence" placeholder="https://… или иной проверяемый URI">
</label>
</div>
          <button id="review-action" class="button" disabled>Записать независимую проверку</button>
          <div class="decision">
<button id="approve" class="button button-approve" disabled>Утвердить baseline · L3</button>
<div class="reject-row">
<input id="rejection" aria-label="Причина отказа" placeholder="Причина отказа">
<button id="reject" class="button button-danger" disabled>Отклонить · L3</button>
</div>
</div>
          <p class="fine">Кнопки доступны после загрузки пакета. AI и служебные токены не получают L3.</p>
        </section>
      </div>
      <footer>Engineering Gateway · staging <span>Источники инженерных данных: Git, StrictDoc, Capella, OpenProject</span>
<a href="?plain=1">Упрощённый вид</a>
</footer>
    </main>
  </div>
</div>
<script src="ui.js" defer>
</script>
</body>
</html>"""

STYLES = """
:root{color-scheme:light;
font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
color:#162b3c;
background:#f3f6f5}

*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0}
button,input,textarea{font:inherit}
button{cursor:pointer}
button:disabled{cursor:not-allowed;
opacity:.5}
a{color:inherit}
.skip{position:absolute;
left:-9999px}
.skip:focus{left:1rem;
top:1rem;
z-index:20;
background:white;
padding:.6rem}

.shell{display:grid;
grid-template-columns:236px minmax(0,1fr);
min-height:100vh}
.sidebar{background:#102333;
color:#d7e5e8;
padding:30px 18px;
display:flex;
flex-direction:column;
position:sticky;
top:0;
height:100vh}
.brand{display:flex;
gap:12px;
align-items:center;
padding:0 12px 42px}
.brand-mark{width:39px;
height:39px;
border:1px solid #517477;
background:#254950;
border-radius:12px;
display:grid;
place-items:center;
color:#a0d0b7;
font-size:23px}
.brand strong{display:block;
letter-spacing:.2em;
font-size:18px}
.brand small{display:block;
color:#9eb4ba;
font-size:11px;
margin-top:3px}
.sidebar-caption{color:#7d9ba1;
font-size:10px;
text-transform:uppercase;
letter-spacing:.16em;
padding:0 12px 12px}
.sidebar nav{display:grid;
gap:4px}
.nav-link{text-decoration:none;
padding:12px 14px;
border-radius:10px;
color:#aec3c7;
font-size:13px}
.nav-link:hover,.nav-link:focus,.nav-link.selected{color:#f8ffff;
background:#25464c}
.nav-link.selected{box-shadow:inset 3px 0 #82caa4}
.sidebar-note{margin-top:auto;
padding:17px 10px;
border-top:1px solid #2d4650;
display:flex;
gap:9px;
color:#9ab2b8;
font-size:11px;
line-height:1.5}
.status-dot{width:7px;
height:7px;
flex:none;
border-radius:50%;
background:#ddb37a;
margin-top:5px}

.content{min-width:0}
.topbar{height:70px;
background:#fff;
border-bottom:1px solid #e4ebea;
display:flex;
justify-content:space-between;
align-items:center;
padding:0 34px;
gap:16px}
.breadcrumb{font-size:13px;
color:#60747e}
.breadcrumb span{color:#b7c4c8;
margin:0 10px}
.auth{display:flex;
align-items:center;
gap:16px}
.identity{font-size:12px;
color:#72858a}
main{max-width:1510px;
margin:auto;
padding:30px 34px 16px}
.hero{position:relative;
overflow:hidden;
min-height:248px;
background:linear-gradient(110deg,#183c47,#1e4e52 58%,#275d59);
border-radius:17px;
color:white;
display:grid;
grid-template-columns:minmax(0,1.2fr) minmax(240px,.8fr);
padding:37px 44px}
.eyebrow{text-transform:uppercase;
font-size:10px;
letter-spacing:.17em;
font-weight:800;
color:#477e70}
.hero .eyebrow{color:#9bd0b5}
.hero h1{font-size:clamp(26px,3vw,42px);
line-height:1.15;
letter-spacing:-.035em;
max-width:650px;
margin:13px 0}
.hero p{color:#c8dcdb;
max-width:590px;
line-height:1.55;
font-size:14px}
.hero-actions{display:flex;
gap:24px;
align-items:center;
margin-top:25px}
.text-link{text-decoration:none;
font-size:12px;
color:#d2e7db}
.button{border:1px solid #d3e0df;
background:white;
color:#21424a;
border-radius:9px;
padding:10px 15px;
font-size:12px;
font-weight:700;
white-space:nowrap}
.button:hover:not(:disabled){filter:brightness(.95)}
.button-small{padding:8px 12px}
.button-primary{background:#79c6a0;
border-color:#79c6a0;
color:#173a39;
text-decoration:none;
display:inline-flex;
gap:14px;
align-items:center}
.hero-art{position:relative;
min-height:170px}
.orbit{position:absolute;
border:1px solid rgba(190,229,216,.32);
border-radius:50%;
left:50%;
top:50%;
transform:translate(-50%,-50%)}
.orbit-a{width:190px;
height:190px}
.orbit-b{width:290px;
height:290px}
.plane{position:absolute;
left:50%;
top:50%;
transform:translate(-50%,-50%) rotate(-30deg);
font-size:96px;
color:#aee0c8;
text-shadow:0 8px 24px #123b40}
.orbit-label{position:absolute;
font-size:9px;
letter-spacing:.14em;
color:#b7dbce}
.orbit-label.one{top:20%;
left:10%}
.orbit-label.two{right:0;
top:44%}
.orbit-label.three{bottom:11%;
left:18%}

.notice{margin:17px 0;
padding:10px 14px;
border-left:3px solid #75b499;
background:#e6f2eb;
border-radius:5px;
color:#33594d;
font-size:12px;
min-height:36px}
.notice.error{border-color:#ce816f;
background:#fff0eb;
color:#7f4134}
.metrics{display:grid;
grid-template-columns:repeat(4,minmax(0,1fr));
gap:15px;
margin:18px 0 22px}
.metric,.panel{background:white;
border:1px solid #e3ebea;
box-shadow:0 3px 18px rgba(18,47,51,.035);
border-radius:14px}
.metric{padding:19px 20px;
min-height:112px}
.metric span,.metric small{display:block;
color:#72868b;
font-size:11px}
.metric strong{display:block;
font-size:21px;
letter-spacing:-.035em;
margin:10px 0 3px;
white-space:nowrap;
overflow:hidden;
text-overflow:ellipsis}
.columns{display:grid;
grid-template-columns:minmax(0,.86fr) minmax(0,1.14fr);
gap:18px;
margin-bottom:18px}
.columns.lower{grid-template-columns:minmax(0,1.14fr) minmax(0,.86fr)}
.panel{padding:25px;
min-width:0;
scroll-margin-top:15px}
.panel-heading{display:flex;
justify-content:space-between;
align-items:flex-start;
gap:12px}
.lifecycle{margin-bottom:18px}
.guide{margin-bottom:18px}
.guide-steps{margin:12px 0 17px;padding-left:22px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 25px;font-size:12px;line-height:1.5;color:#49646b}
.guide-steps li{padding-left:3px}
.baseline-guide{border:1px solid #cbded6;background:#f4f9f6;border-radius:9px;padding:14px 16px;font-size:12px;line-height:1.55;color:#3f625a}
.baseline-guide p{margin:7px 0 0}
.memory-state{font-size:11px;color:#275d4b;font-weight:700;margin:-4px 0 8px}
.memory-detail{font-size:11px;color:#637d79;margin-bottom:10px}
.memory-detail summary{cursor:pointer}
.memory-detail p{line-height:1.45;margin:7px 0}
.lifecycle-steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:7px}
.lifecycle-steps li{min-width:0;border:1px solid #e1eae7;background:#f8faf9;border-radius:9px;padding:12px 9px;position:relative}
.lifecycle-steps li::before{content:counter(list-item, decimal-leading-zero);display:block;font-size:10px;font-weight:800;color:#7e9992;margin-bottom:7px}
.lifecycle-steps strong,.lifecycle-steps small{display:block;overflow-wrap:anywhere}
.lifecycle-steps strong{font-size:11px;color:#46646a}
.lifecycle-steps small{font-size:9px;color:#829599;line-height:1.4;margin-top:5px}
.lifecycle-steps li.current{background:#e4f4e9;border-color:#68b88c;box-shadow:inset 0 0 0 1px #68b88c}
.lifecycle-steps li.current::before,.lifecycle-steps li.current strong{color:#236a4d}
.panel h2{font-size:21px;
letter-spacing:-.025em;
margin:7px 0 10px}
.muted{font-size:12px;
color:#6e8187;
line-height:1.55;
margin:0 0 19px}
.badge{display:inline-flex;
align-items:center;
border-radius:100px;
padding:6px 10px;
background:#e7f3eb;
color:#397157;
font-size:10px;
font-weight:700;
white-space:nowrap}
.badge-muted{background:#edf1f2;
color:#6e7d83}
.badge-warn{background:#fff3e5;
color:#9a6c35}
.agent-list{display:grid;
grid-template-columns:repeat(2,minmax(0,1fr));
gap:8px}
.agent{display:flex;
gap:11px;
padding:11px;
border:1px solid #e6eeec;
border-radius:9px;
min-width:0}
.agent-icon{display:grid;
place-items:center;
flex:none;
width:32px;
height:32px;
border-radius:9px;
background:#e9f2ee;
color:#367d68;
font-size:12px;
font-weight:800}
.agent-body{min-width:0}
.agent strong,.agent small{display:block}
.agent strong{font-size:12px}
.agent small{color:#8a9a9f;
font-size:10px;
margin-top:4px;
line-height:1.4}
.agent-task{font-size:10px;
color:#526e72;
margin-top:6px}
.callout{display:flex;
gap:12px;
background:#f2f8f5;
border:1px solid #dfede5;
border-radius:9px;
padding:13px;
margin-top:15px;
font-size:11px;
line-height:1.5}
.callout strong{min-width:100px;
color:#37685b}
.callout span{color:#607d77}
.empty{font-size:12px;
color:#809396}

.workspace-form label,.form-grid label{display:block;
font-size:11px;
font-weight:700;
color:#47606a}
.project-start{display:grid;gap:9px;border:1px solid #dcebe4;border-radius:10px;background:#f8fbf9;padding:16px;margin-bottom:22px}
.project-start h3{margin:0 0 4px;font-size:15px}
.project-start label{font-size:11px;font-weight:700;color:#47606a}
.project-start small{font-size:10px;color:#72868b;line-height:1.5}
.project-start .button{justify-self:start}
.draft-list{display:grid;gap:7px;margin-top:6px}
.draft-item{border:1px solid #dce8e3;border-radius:7px;background:white;padding:10px;font-size:11px;overflow-wrap:anywhere}
.draft-item strong,.draft-item small{display:block;margin-bottom:4px}
.draft-item .button{margin-top:8px}
.project-feedback{font-size:11px;line-height:1.5;color:#37685b}
.project-feedback.error{color:#9b5143}
.chat-project{font-size:11px;color:#37685b;background:#f2f8f5;border-radius:7px;padding:9px;margin-bottom:11px;line-height:1.5}
.input-row{display:flex;
gap:8px;
margin:8px 0 5px}
.input-row input{flex:1;
min-width:0}
.workspace-form small{font-size:10px;
color:#8b9a9e}
.project-meta{display:flex;
flex-wrap:wrap;
gap:7px;
margin:18px 0 12px}
.project-meta span{background:#f1f5f4;
border-radius:6px;
color:#5b7378;
font-size:10px;
padding:6px 8px}
.graph-empty{min-height:130px;
background:#f8faf9;
border:1px dashed #cfddda;
border-radius:9px;
display:grid;
place-items:center;
text-align:center;
color:#91a2a3;
font-size:12px;
padding:18px}
.graph-list{display:grid;
gap:9px}
.graph-item{display:flex;
align-items:flex-start;
gap:10px;
padding:10px;
background:#f8faf9;
border:1px solid #e4ecea;
border-radius:8px}
.graph-kind{background:#deeee7;
color:#357764;
border-radius:5px;
font-size:9px;
font-weight:800;
text-transform:uppercase;
padding:5px 7px}
.graph-item strong{font-size:12px}
.graph-item small{display:block;
color:#819499;
font-size:10px;
margin-top:4px;
overflow-wrap:anywhere}
.relations{font-size:11px;
color:#627a7e;
margin-top:10px}
.relation-list{display:grid;
gap:6px;
margin-top:8px}
.relation-item{display:flex;
flex-wrap:wrap;
gap:7px;
align-items:center;
padding:8px 10px;
background:#f3f8f6;
border-radius:7px;
font-size:10px;
overflow-wrap:anywhere}
.relation-item b{color:#3c7866;
font-size:9px;
font-weight:800}
.raw{margin-top:15px;
border-top:1px solid #edf1f0;
padding-top:12px}
.raw summary{font-size:11px;
color:#42766d;
cursor:pointer}
.raw pre{font-size:10px;
line-height:1.5;
overflow:auto;
max-height:260px;
background:#f6f8f7;
padding:12px;
border-radius:7px}

input,textarea{border:1px solid #d5e0de;
background:white;
border-radius:8px;
color:#17313a;
padding:10px 11px;
outline:none}
input:focus,textarea:focus{border-color:#4b9b7e;
box-shadow:0 0 0 3px #dff2e8}
textarea{width:100%;
resize:vertical;
font-size:12px}
.conversation{height:260px;
overflow:auto;
display:flex;
flex-direction:column;
gap:12px;
background:#f8faf9;
border:1px solid #e8efed;
border-radius:9px;
padding:14px;
margin-bottom:12px}
.welcome{display:flex;
gap:10px;
align-items:start;
font-size:12px;
color:#647b7b;
line-height:1.5}
.welcome p{margin:4px 0}
.avatar{display:grid;
place-items:center;
flex:none;
width:28px;
height:28px;
background:#deefe5;
color:#408469;
border-radius:8px}
.turn{font-size:12px;
line-height:1.5;
max-width:90%;
padding:10px 13px;
border-radius:11px;
white-space:pre-wrap;
overflow-wrap:anywhere}
.turn.user{align-self:end;
background:#dff1e7}
.turn.assistant{align-self:start;
background:white;
border:1px solid #e1eae6}
.turn strong{display:block;
font-size:10px;
color:#557970;
margin-bottom:4px}
.turn.assistant{white-space:normal}
.turn.assistant p{margin:0 0 8px}
.turn.assistant p:last-child{margin-bottom:0}
.turn.assistant ul,.turn.assistant ol{padding-left:20px;margin:6px 0}
.turn.assistant li{margin:4px 0}
.turn.assistant pre{overflow:auto;background:#eef5f1;border-radius:6px;padding:8px}
.turn.assistant code{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}
.turn.assistant a{color:#236b66;text-decoration:underline}
.turn.assistant blockquote{border-left:3px solid #80b69a;margin:8px 0;padding-left:10px}
.chat-footer{display:flex;
justify-content:space-between;
align-items:center;
gap:12px;
margin-top:9px}
.check{display:flex;
align-items:center;
gap:6px;
font-size:11px;
color:#60777c}
.check input{accent-color:#438b71}
.step{display:flex;
align-items:center;
gap:10px;
margin:15px 0}
.step>span{width:26px;
height:26px;
display:grid;
place-items:center;
border-radius:50%;
background:#e6f2eb;
color:#47846d;
font-size:11px;
font-weight:800;
flex:none}
.step strong,.step small{display:block}
.step strong{font-size:11px}
.step small{font-size:10px;
color:#809097;
margin-top:3px}
.form-grid{display:grid;
grid-template-columns:1fr 1fr;
gap:10px;
margin:22px 0 12px}
.form-grid input{display:block;
width:100%;
margin-top:6px;
font-size:11px}
.decision{border-top:1px solid #e9eeee;
margin-top:18px;
padding-top:18px}
.button-approve{background:#315f50;
border-color:#315f50;
color:white}
.reject-row{display:flex;
gap:8px;
margin-top:10px}
.reject-row input{min-width:0;
flex:1;
font-size:11px}
.button-danger{color:#9b5143;
border-color:#eddad4}
.fine{font-size:10px;
color:#87999a;
line-height:1.5}
footer{display:flex;
justify-content:space-between;
gap:12px;
padding:20px 0;
color:#91a2a4;
font-size:10px}
.sr-only{position:absolute;
width:1px;
height:1px;
padding:0;
margin:-1px;
overflow:hidden;
clip:rect(0,0,0,0);
white-space:nowrap;
border:0}

@media(max-width:1050px){.shell{grid-template-columns:1fr}
.lifecycle-steps{grid-template-columns:repeat(4,minmax(0,1fr))}
.sidebar{position:static;
height:auto;
padding:12px 18px}
.brand{padding:0 0 10px}
.sidebar-caption,.sidebar-note{display:none}
.sidebar nav{display:flex;
overflow:auto}
.nav-link{white-space:nowrap;
padding:8px 12px}
.columns,.columns.lower{grid-template-columns:1fr}
.guide-steps{grid-template-columns:1fr}
.hero-art{display:none}
.hero{grid-template-columns:1fr}
}
@media(max-width:650px){.topbar{padding:12px 16px;
height:auto;
align-items:flex-start}
.lifecycle-steps{grid-template-columns:repeat(2,minmax(0,1fr))}
/* Keep mobile painting simple on older Android WebView/Chrome compositors. */
.shell{display:block;
min-height:0}
.sidebar{position:relative;
height:auto;
display:block}
.hero{background:#214c50}
.metric,.panel{box-shadow:none}
.orbit,.plane{display:none}
html{scroll-behavior:auto}
.breadcrumb{display:none}
.auth{width:100%;
justify-content:space-between}
main{padding:16px}
.hero{padding:25px}
.hero h1{font-size:28px}
.metrics{grid-template-columns:repeat(2,minmax(0,1fr));
gap:8px}
.metric{padding:13px;
min-height:90px}
.metric strong{font-size:16px}
.panel{padding:17px}
.agent-list,.form-grid{grid-template-columns:1fr}
.input-row,.reject-row{flex-direction:column}
.chat-footer{align-items:stretch;
flex-direction:column}
.chat-footer button{justify-content:center}
footer span{display:none}
}

"""

SCRIPT = r"""'use strict';
const $ = id => document.getElementById(id);
const status = (message, error=false) => { $('status').textContent = message; $('status').classList.toggle('error', error); };
const b64url = bytes => btoa(String.fromCharCode(...new Uint8Array(bytes)))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
let config, token, loadedPackage, selectedProjectId, startProposal;
let refreshToken, tokenExpiresAt = 0;
const redirect = location.origin + '/human/';
const sessionIntent = 'gateway_session_intent';
async function loadConfig() {
  const response = await fetch('/human/config', {cache: 'no-store'});
  if (!response.ok) throw Error('Не удалось получить настройки IdP');
  config = await response.json();
}
async function login(silent=false) {
  if (!config) await loadConfig();
  const verifier = b64url(crypto.getRandomValues(new Uint8Array(32)));
  const state = b64url(crypto.getRandomValues(new Uint8Array(24)));
  sessionStorage.setItem('gateway_pkce', JSON.stringify({verifier, state, silent}));
  const challenge = b64url(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
  const url = new URL(config.issuer + '/protocol/openid-connect/auth');
  url.search = new URLSearchParams({client_id: config.client_id, redirect_uri: redirect,
    response_type: 'code', scope: 'openid', code_challenge_method: 'S256', code_challenge: challenge,
    state, ...(silent ? {prompt:'none'} : {})}).toString();
  location.assign(url.toString());
}
async function finishLogin() {
  const params = new URLSearchParams(location.search);
  if (!params.has('code') && !params.has('error')) return false;
  history.replaceState(null, '', redirect);
  const saved = JSON.parse(sessionStorage.getItem('gateway_pkce') || 'null');
  sessionStorage.removeItem('gateway_pkce');
  if (params.has('error') && saved?.silent) {
    sessionStorage.removeItem(sessionIntent);
    status('Сессия Keycloak закончилась. Войдите снова.');
    return true;
  }
  if (params.has('error')) throw Error('IdP отказал во входе: ' + params.get('error'));
  if (!saved || params.get('state') !== saved.state) throw Error('OIDC state не совпадает');
  const response = await fetch(config.issuer + '/protocol/openid-connect/token', {
    method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({grant_type:'authorization_code', client_id:config.client_id,
      redirect_uri:redirect, code:params.get('code'), code_verifier:saved.verifier})});
  if (!response.ok) throw Error('Не удалось обменять код входа');
  const data = await response.json();
  token = data.access_token;
  refreshToken = data.refresh_token;
  tokenExpiresAt = Date.now() + (data.expires_in || 60) * 1000;
  sessionStorage.setItem(sessionIntent, '1');
  $('identity').textContent = 'Вход выполнен';
  $('login').hidden = true;
  status('Вход выполнен. После обновления страницы сессия восстановится через Keycloak.');
  const results = await Promise.allSettled([loadActivity(), loadProjects()]);
  for (const result of results) if (result.status === 'rejected') status(result.reason.message, true);
  return true;
}
async function renewToken() {
  if (!refreshToken || Date.now() < tokenExpiresAt - 30000) return;
  const response = await fetch(config.issuer + '/protocol/openid-connect/token', {
    method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({grant_type:'refresh_token', client_id:config.client_id,
      refresh_token:refreshToken})});
  if (!response.ok) { token = undefined; throw Error('Сессия истекла. Войдите снова и повторите действие.'); }
  const data = await response.json();
  token = data.access_token;
  refreshToken = data.refresh_token;
  tokenExpiresAt = Date.now() + (data.expires_in || 60) * 1000;
}
async function api(path, method='GET', body) {
  if (!token) throw Error('Сначала войдите через Keycloak');
  await renewToken();
  const response = await fetch('/human/' + path, {
    method, headers: {Authorization: 'Bearer ' + token, ...(body ? {'Content-Type':'application/json'} : {})},
    body: body ? JSON.stringify(body) : undefined, cache: 'no-store'});
  const data = await response.json();
  if (response.status === 401) {
    token = undefined;
    $('identity').textContent = 'Сессия истекла';
    $('login').hidden = false;
    throw Error('Сессия истекла. Войдите снова и повторите действие.');
  }
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data));
  return data;
}
function run(fn) { return () => fn().catch(error => status(error.message, true)); }
function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}
async function loadActivity() {
  const data = await api('assistant/activity');
  renderAgents(data);
}
function selectProject(project, discuss=false) {
  selectedProjectId = project.id;
  startProposal = undefined;
  $('start-form').hidden = true;
  $('start-confirmed').checked = false;
  sessionStorage.setItem('gateway_selected_project', project.id);
  $('memory-state').textContent = 'Контекст Alice: загружаем сохранённый диалог…';
  loadDialogue(project.id, project.version, project.source_hash).catch(error => status(error.message, true));
  const stage = project.state === 'draft' && !project.baseline_id ? 'draft' : null;
  for (const item of document.querySelectorAll('.lifecycle-steps li')) {
    const current = item.dataset.stage === stage;
    item.classList.toggle('current', current);
    if (current) item.setAttribute('aria-current', 'step');
    else item.removeAttribute('aria-current');
  }
  $('lifecycle-badge').textContent = stage ? 'Замысел · черновик' : 'Состояние требует проверки';
  $('lifecycle-summary').textContent = project.name + ' · версия ' + project.version +
    ' · источник: ввод человека · SHA-256: ' + project.source_hash +
    (stage ? '. Следующий этап — первая рабочая область с открытым Change Request.' : '. Этап не определён по черновику.');
  $('chat-project').textContent = 'Исходный черновик: ' + project.name + ' · версия ' + project.version +
    ' · SHA-256: ' + project.source_hash + '. Alice получит его текст только после отправки сообщения.';
  if (discuss) {
    $('message').value = 'Какие исходные сведения и ограничения мне нужно уточнить для проектирования этого БПЛА? Задай конкретные вопросы, не создавая утверждённых требований.';
    location.hash = 'assistant';
    $('message').focus();
  }
}
async function loadDialogue(projectId, version, sourceHash) {
  const data = await api('projects/' + encodeURIComponent(projectId) + '/dialogue');
  if (selectedProjectId !== projectId) return;
  showMemory(data.total_turns, data.next_context_turns, version, sourceHash);
  $('conversation').replaceChildren();
  if (!data.turns.length) {
    $('conversation').append(element('p', 'empty', 'Диалог пока пуст. Исходный черновик будет передан Alice с вашим первым сообщением.'));
  }
  for (const turn of data.turns) addTurn(turn.role, turn.text, turn.answer_html);
}
function showMemory(total, included, version, sourceHash) {
  let label = 'Сохранено ' + total + ' реплик · в следующий запрос Alice войдут ' + included;
  if (version !== undefined) label += ' · черновик v' + version + ' · SHA-256 ' + sourceHash.slice(0, 12);
  $('memory-state').textContent = label;
}
async function loadProjects() {
  const data = await api('projects');
  const list = $('draft-list');
  list.replaceChildren();
  if (!data.projects.length) { list.append(element('p', 'empty', 'Пока нет черновиков. Опишите первый проект выше.')); return; }
  const preferred = sessionStorage.getItem('gateway_selected_project');
  selectProject(data.projects.find(project => project.id === preferred) || data.projects[0]);
  for (const project of data.projects) {
    const card = element('div', 'draft-item');
    card.append(element('strong', '', project.name),
      element('small', '', 'Черновик · версия ' + project.version + ' · ' + project.created_at),
      element('div', '', project.goal),
      element('small', '', 'Автор: ' + project.author_id + ' · SHA-256: ' + project.source_hash));
    if (project.constraints) card.append(element('div', '', 'Ограничения: ' + project.constraints));
    const choose = element('button', 'button', 'Выбрать проект');
    choose.type = 'button';
    choose.onclick = () => selectProject(project);
    const discuss = element('button', 'button', 'Обсудить с Alice');
    discuss.type = 'button';
    discuss.onclick = () => selectProject(project, true);
    card.append(choose, document.createTextNode(' '), discuss);
    list.append(card);
  }
}
async function loadExamples() {
  const response = await fetch('/human/examples', {cache:'no-store'});
  if (!response.ok) throw Error('Не удалось загрузить демонстрационные проекты');
  const data = await response.json();
  const list = $('example-list');
  list.replaceChildren();
  for (const example of data.examples) {
    const card = element('div', 'draft-item');
    card.append(element('strong', '', example.name),
      element('small', '', 'Демонстрация · ' + example.profile.id + '@' + example.profile.version +
        ' · ' + example.elements.length + ' элементов · ' + example.relations.length + ' связей'),
      element('p', '', example.goal));
    const inspect = element('details', 'raw');
    inspect.append(element('summary', '', 'Посмотреть содержание и трассировку'));
    for (const item of example.elements) {
      inspect.append(element('p', '', item.type_id + ' · ' + item.name + ': ' + item.detail));
    }
    for (const [source, relation, target] of example.relations) {
      inspect.append(element('small', '', source + ' → ' + relation + ' → ' + target));
      inspect.append(document.createElement('br'));
    }
    card.append(inspect);
    const use = element('button', 'button', 'Взять как основу нового черновика');
    use.type = 'button';
    use.onclick = () => {
      $('new-name').value = example.name;
      $('new-goal').value = example.goal;
      $('new-constraints').value = example.constraints;
      location.hash = 'project';
      $('new-name').focus();
    };
    card.append(use);
    list.append(card);
  }
}
function renderAgents(data) {
  const list = $('agent-list');
  list.replaceChildren();
  for (const agent of data.agents) {
    const card = element('div', 'agent');
    card.append(element('span', 'agent-icon', agent.name.slice(0, 1)));
    const body = element('div', 'agent-body');
    body.append(element('strong', '', agent.name), element('small', '', agent.purpose || ''));
    body.append(element('div', 'agent-task', agent.status === 'running' ? ('В работе: ' + (agent.task || 'задача не указана')) :
      agent.status === 'idle' ? 'Ожидает задачи' : 'Активность не наблюдается'));
    card.append(body); list.append(card);
  }
  const active = data.agents.filter(agent => agent.status === 'running').length;
  $('metric-agents').textContent = data.telemetry === 'connected' ? String(active) : 'Неизвестно';
  $('metric-telemetry').textContent = data.telemetry === 'connected' ? 'По данным оркестратора' : 'Телеметрия не подключена';
  $('team-badge').textContent = data.telemetry === 'connected' ? 'Данные оркестратора' : 'Нет телеметрии';
}
async function loadStructure() {
  const response = await fetch('/human/structure', {cache:'no-store'});
  if (!response.ok) throw Error('Не удалось загрузить структуру ролей');
  const data = await response.json();
  renderAgents({telemetry:'unavailable', agents:data.agents});
}
function renderProject(data) {
  loadedPackage = data;
  const workspace = data.workspace || {};
  const changes = data.changes || {};
  const elements = Array.isArray(changes.elements) ? changes.elements : [];
  const relations = Array.isArray(changes.relations) ? changes.relations : [];
  $('metric-workspace').textContent = workspace.state || 'Загружена';
  $('metric-workspace-detail').textContent = 'Версия ' + (workspace.version ?? '—');
  $('metric-graph').textContent = elements.length + ' / ' + relations.length;
  $('metric-review').textContent = workspace.state === 'ready_for_approval' && workspace.reconciled ? 'Проверьте evidence' : 'Не готова';
  const meta = $('project-meta');
  meta.replaceChildren();
  for (const value of ['Профиль: ' + (workspace.profile_id || 'не указан'), 'Версия: ' + (workspace.profile_version || '—'),
    'Git: ' + (workspace.source_git_commit || '—').slice(0, 12), 'Состояние: ' + (workspace.state || '—')]) meta.append(element('span', '', value));
  const graph = $('project-graph');
  graph.replaceChildren();
  if (!elements.length) graph.append(element('p', '', 'В области пока нет записанных элементов.'));
  else {
    const list = element('div', 'graph-list');
    for (const item of elements.slice(0, 40)) {
      const row = element('div', 'graph-item');
      row.append(element('span', 'graph-kind', item.kind || 'элемент'));
      const detail = element('div');
      detail.append(element('strong', '', item.name || item.external_id || 'Без названия'),
        element('small', '', (item.external_system || '—') + ' · ' + (item.external_id || item.id || '—')));
      row.append(detail); list.append(row);
    }
    graph.append(list);
    if (elements.length > 40) graph.append(element('p', 'relations', 'Показаны первые 40 элементов. Полный список — в исходном пакете.'));
  }
  graph.append(element('p', 'relations', 'Типизированных связей в изменениях: ' + relations.length));
  if (relations.length) {
    const byId = new Map(elements.map(item => [item.id, item.name || item.external_id || item.id]));
    const links = element('div', 'relation-list');
    for (const link of relations.slice(0, 30)) {
      const row = element('div', 'relation-item');
      row.append(element('span', '', byId.get(link.source_id) || link.source_id || 'Внешний элемент'),
        element('b', '', link.relation_type || 'связь'),
        element('span', '', byId.get(link.target_id) || link.target_id || 'Внешний элемент'));
      links.append(row);
    }
    graph.append(links);
    if (relations.length > 30) graph.append(element('p', 'relations', 'Показаны первые 30 связей. Полный список — в пакете.'));
  }
  $('package').textContent = JSON.stringify(data, null, 2);
  for (const id of ['review-action', 'approve', 'reject']) $(id).disabled = false;
}
function addTurn(role, message, safeHtml) {
  const line = element('div', 'turn ' + role);
  line.append(element('strong', '', role === 'user' ? 'Вы' : 'Alice'));
  if (role === 'assistant' && safeHtml) {
    const formatted = element('div', 'formatted-answer');
    formatted.innerHTML = safeHtml; // Gateway renders Markdown and sanitizes HTML on the server.
    for (const link of formatted.querySelectorAll('a')) { link.target = '_blank'; link.rel = 'noopener noreferrer'; }
    line.append(formatted);
  } else line.append(document.createTextNode(message));
  $('conversation').append(line);
  $('conversation').scrollTop = $('conversation').scrollHeight;
}
function selectedWorkspace() {
  if (!loadedPackage || loadedPackage.workspace?.id !== $('workspace').value.trim())
    throw Error('Сначала загрузите пакет выбранной рабочей области');
  return encodeURIComponent(loadedPackage.workspace.id);
}
window.addEventListener('DOMContentLoaded', () => {
  $('login').onclick = run(() => login());
  $('create-project').onclick = async () => {
    const feedback = $('project-feedback');
    feedback.classList.remove('error');
    feedback.textContent = 'Сохраняем черновик…';
    $('create-project').disabled = true;
    try {
    const name = $('new-name').value.trim(), goal = $('new-goal').value.trim();
    if (name.length < 2 || goal.length < 10) throw Error('Укажите название и цель не короче 10 символов');
    const draft = await api('projects', 'POST', {name, goal, constraints:$('new-constraints').value.trim()});
    feedback.textContent = 'Черновик сохранён: ' + draft.id + ' · версия ' + draft.version;
    status('Черновик ' + draft.id + ' сохранён, версия ' + draft.version + '. Это исходные данные, не baseline.');
    try { await loadProjects(); }
    catch (error) { feedback.textContent += '. Список не обновился: ' + error.message; }
    } catch (error) {
      feedback.classList.add('error');
      feedback.textContent = 'Не удалось создать черновик: ' + error.message;
    } finally { $('create-project').disabled = false; }
  };
  $('create-workspace').onclick = async () => {
    const feedback = $('workspace-feedback');
    feedback.classList.remove('error');
    $('create-workspace').disabled = true;
    try {
      if (!selectedProjectId) throw Error('Сначала выберите черновик проекта');
      const change_request_id = $('initial-cr').value.trim();
      const git_repository = $('initial-repo').value.trim();
      const git_ref = $('initial-ref').value.trim();
      if (!change_request_id || !git_repository || !git_ref) throw Error('Укажите Change Request, Git-репозиторий и ref');
      const result = await api('projects/' + encodeURIComponent(selectedProjectId) + '/workspaces', 'POST',
        {change_request_id, git_repository, git_ref});
      $('workspace').value = result.workspace_id;
      feedback.textContent = 'Рабочая область ' + result.workspace_id + ' создана из Git commit ' + result.source_git_commit + '. Загрузите пакет для проверки.';
      status('Первая рабочая область создана без утверждённого baseline.');
    } catch (error) {
      feedback.classList.add('error');
      feedback.textContent = 'Не удалось создать область: ' + error.message;
    } finally { $('create-workspace').disabled = false; }
  };
  $('workspace').addEventListener('input', () => {
    for (const id of ['review-action', 'approve', 'reject']) $(id).disabled = true;
    $('metric-review').textContent = 'Не проверена';
  });
  $('load').onclick = run(async () => {
    const id = $('workspace').value.trim();
    if (!id) throw Error('Введите UUID рабочей области');
    const data = await api('workspaces/' + encodeURIComponent(id));
    renderProject(data);
    status('Пакет загружен. Проверьте версии, хэши и исходные артефакты.');
  });
  $('send').onclick = run(async () => {
    if (!token) throw Error('Сначала войдите через Keycloak');
    const message = $('message').value.trim();
    if (!message) throw Error('Введите сообщение');
    startProposal = undefined;
    $('start-form').hidden = true;
    const workspace_id = $('include-workspace').checked ? $('workspace').value.trim() : null;
    if ($('include-workspace').checked) selectedWorkspace();
    $('send').disabled = true;
    $('alice-state').textContent = 'Отвечает сейчас';
    try {
      const data = await api('assistant/chat', 'POST', {
        message, workspace_id, project_id:selectedProjectId || null});
      addTurn('user', message); addTurn('assistant', data.answer, data.answer_html);
      if (data.memory) {
        const m = data.memory;
        $('memory-state').textContent = 'Alice получила ' + m.context_turns_sent + ' из ' +
          m.stored_turns_before + ' сохранённых реплик · черновик v' + m.project_version +
          ' · SHA-256 ' + m.project_source_hash.slice(0, 12) +
          '. Теперь сохранено ' + m.stored_turns_after + ' реплик.';
      } else $('memory-state').textContent = 'Диалог без выбранного проекта не сохраняется.';
      $('message').value = '';
    } finally { $('send').disabled = false; $('alice-state').textContent = 'Ожидает запроса'; }
  });
  $('prepare-start').onclick = run(async () => {
    if (!selectedProjectId) throw Error('Сначала выберите черновик проекта');
    $('prepare-start').disabled = true;
    $('start-feedback').textContent = 'Alice собирает данные…';
    try {
      const data = await api('projects/' + encodeURIComponent(selectedProjectId) + '/start-form', 'POST');
      if (!data.ready) {
        startProposal = undefined;
        $('start-form').hidden = true;
        const questions = data.questions.length ? data.questions.join('\n') : 'Уточните цель проекта в диалоге.';
        $('start-feedback').textContent = 'Для формы нужны ответы: ' + questions;
        addTurn('assistant', questions);
        return;
      }
      startProposal = {projectId:selectedProjectId, ...data};
      $('start-title').value = data.title;
      $('start-description').value = data.description;
      $('start-sources').textContent = 'Черновик SHA-256: ' + data.draft_source_hash +
        '\nGit commit: ' + data.source_git_commit + '\nИсходные системы: ' +
        data.source_external_versions.map(item => item.system + ' @ ' + item.version).join(', ');
      $('start-confirmed').checked = false;
      $('start-form').hidden = false;
      $('start-feedback').textContent = 'Проверьте и при необходимости исправьте данные перед подтверждением.';
    } finally { $('prepare-start').disabled = false; }
  });
  $('confirm-start').onclick = run(async () => {
    if (!startProposal || startProposal.projectId !== selectedProjectId) throw Error('Соберите форму заново');
    if (!$('start-confirmed').checked) throw Error('Подтвердите проверку формы');
    $('confirm-start').disabled = true;
    try {
      const result = await api('projects/' + encodeURIComponent(selectedProjectId) + '/start', 'POST', {
        confirmed:true, draft_source_hash:startProposal.draft_source_hash,
        title:$('start-title').value.trim(), description:$('start-description').value.trim(),
        source_git_commit:startProposal.source_git_commit,
        source_external_versions:startProposal.source_external_versions});
      $('workspace').value = result.workspace_id;
      $('initial-cr').value = result.change_request_id;
      $('start-feedback').textContent = 'Создан OpenProject #' + result.openproject_id +
        ', рабочая область ' + result.workspace_id + '. Загрузите пакет области.';
      $('start-form').hidden = true;
      startProposal = undefined;
    } finally { $('confirm-start').disabled = false; }
  });
  $('review-action').onclick = run(async () => {
    await api('workspaces/' + selectedWorkspace() + '/review', 'POST',
      {accepted:true, reason:$('reason').value, evidence_uri:$('evidence').value});
    status('Независимая проверка записана.');
  });
  $('approve').onclick = run(async () => {
    if (!confirm('Вы лично проверили содержимое и утверждаете baseline?')) return;
    const result = await api('workspaces/' + selectedWorkspace() + '/approve', 'POST');
    status('Baseline: ' + result.baseline_id + ', Git tag: ' + result.git_tag);
  });
  $('reject').onclick = run(async () => {
    if (!confirm('Отклонить рабочую область?')) return;
    await api('workspaces/' + selectedWorkspace() + '/reject', 'POST',
      {reason:$('rejection').value}); status('Рабочая область отклонена.');
  });
  run(async () => {
    await loadConfig();
    loadStructure().catch(error => status(error.message, true));
    loadExamples().catch(error => status(error.message, true));
    const returnedFromIdp = await finishLogin();
    if (!returnedFromIdp && sessionStorage.getItem(sessionIntent)) await login(true);
  })();
});
"""
