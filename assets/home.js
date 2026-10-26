/* 首页：统计和年级入口都从 data/*.json 计算，不写死数量。 */
(function () {
  'use strict';
  var raw = location.hash.replace(/^#/, '');
  try { raw = decodeURIComponent(raw); } catch (e) { /* 保持原样 */ }
  if (/^(?:cnm|cne|cnp|cnc)_[A-Za-z0-9]+$/.test(raw)) return;

  var subjectParam = new URLSearchParams(location.search).get('subject');
  var subject = subjectParam === 'english' || subjectParam === 'physics' ? subjectParam : 'math';
  var PREFIX = { math: 'cnm_', english: 'cne_', physics: 'cnp_' };
  var STD_PREFIX = { math: 'cms-', english: 'ces-', physics: 'cps-' };

  function withSubject(href) {
    if (subject === 'math' || !href || href.indexOf('subject=') >= 0 || href.indexOf('http') === 0) return href;
    return href + (href.indexOf('?') >= 0 ? '&' : '?') + 'subject=' + subject;
  }

  document.body.classList.toggle('subject-english', subject === 'english');
  document.body.classList.toggle('subject-physics', subject === 'physics');
  document.querySelectorAll('.subject-link').forEach(function (link) {
    var on = link.getAttribute('data-subject') === subject;
    link.classList.toggle('on', on);
    if (on) link.setAttribute('aria-current', 'true');
    else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('.site-nav a:not(.subject-link), a.brand').forEach(function (link) {
    var href = link.getAttribute('href');
    var next = withSubject(href);
    if (next && next !== href) link.setAttribute('href', next);
  });
  if (subject === 'english') {
    document.title = '英语 · 中小学·高中知识图谱';
    var eye = document.querySelector('.eyebrow');
    if (eye) eye.textContent = '英语：小一至中六';
    var primary = document.querySelector('.hero-actions a.btn-primary');
    var browse = document.querySelector('.hero-actions a.btn:not(.btn-primary)');
    if (primary) primary.setAttribute('href', 'diagnose/?subject=english');
    if (browse) browse.setAttribute('href', 'explore/?subject=english');
    var demo = document.querySelector('.quiet-link a');
    if (demo) {
      demo.setAttribute('href', 'diagnose/?subject=english&target=cne_p148&demo=1');
      demo.textContent = '先看一遍演示：现在进行时';
    }
  } else if (subject === 'physics') {
    document.title = '物理 · 中小学·高中知识图谱';
    var peye = document.querySelector('.eyebrow');
    if (peye) peye.textContent = '物理：中一至中三科学 · 中四至中六物理';
    var pprimary = document.querySelector('.hero-actions a.btn-primary');
    var pbrowse = document.querySelector('.hero-actions a.btn:not(.btn-primary)');
    if (pprimary) pprimary.setAttribute('href', 'diagnose/?subject=physics');
    if (pbrowse) pbrowse.setAttribute('href', 'explore/?subject=physics');
    var pdemo = document.querySelector('.quiet-link a');
    if (pdemo) {
      pdemo.setAttribute('href', 'diagnose/?subject=physics&target=cnp_071&demo=1');
      pdemo.textContent = '先看一遍演示：欧姆定律';
    }
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) node.textContent = value;
  }

  function fail(message) {
    var box = document.getElementById('load-error');
    if (!box) return;
    box.hidden = false;
    box.textContent = message;
  }

  Promise.all([
    fetch('data/topics.json'),
    fetch('data/dependencies.json'),
    fetch('data/questions.json'),
    fetch('data/edb-standards.json')
  ]).then(function (responses) {
    responses.forEach(function (response, index) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
    });
    return Promise.all(responses.map(function (response) { return response.json(); }));
  }).then(function (data) {
    var topics = data[0];
    var deps = data[1];
    var questions = data[2];
    var standards = data[3];
    if (!Array.isArray(topics) || !Array.isArray(deps) || !Array.isArray(questions)) {
      throw new Error('数据格式无法识别');
    }
    var items = standards && Array.isArray(standards.items) ? standards.items : [];
    function subjectOfId(id) {
      id = String(id || '');
      if (id.indexOf('cne_') === 0) return 'english';
      if (id.indexOf('cnp_') === 0) return 'physics';
      return 'math';
    }
    function subjectOfStd(id) {
      id = String(id || '');
      if (id.indexOf('edb-english:') === 0) return 'english';
      if (id.indexOf('edb-physics:') === 0) return 'physics';
      return 'math';
    }
    var wantEnglish = subject === 'english';
    var wantPhysics = subject === 'physics';
    topics = topics.filter(function (topic) { return (topic.subject || subjectOfId(topic.id)) === subject; });
    deps = deps.filter(function (edge) { return subjectOfId(edge.topicId) === subject; });
    questions = questions.filter(function (question) { return subjectOfId(question.topicId) === subject; });
    items = items.filter(function (item) { return subjectOfStd(item.id) === subject; });
    setText('n-topics', String(topics.length));
    setText('n-edges', String(deps.length));
    setText('n-questions', String(questions.length));
    setText('n-standards', String(items.length));

    var grades = document.getElementById('grades');
    if (!grades) return;
    grades.replaceChildren();
    grades.removeAttribute('aria-busy');

    /* 香港：小学按小一…小六，初中、高中各一个阶段（EDB 的单元不指定年级）。 */
    var byStage = new Map();
    topics.forEach(function (topic) {
      var key = topic.stage || String(topic.grade);
      if (!byStage.has(key)) {
        byStage.set(key, {
          label: topic.stageLabel || '',
          grade: topic.grade,
          keyStage: topic.keyStage,
          topics: []
        });
      }
      byStage.get(key).topics.push(topic);
    });

    Array.from(byStage.values())
      .sort(function (a, b) { return a.grade - b.grade; })
      .forEach(function (group) {
        var units = new Set(group.topics.map(function (t) { return t.unit; }));
        var band = group.keyStage === 'KS1' || group.keyStage === 'KS2' ? '小学'
          : group.keyStage === 'KS3' ? '初中' : '高中';
        var klass = band === '小学' ? 'is-primary' : band === '初中' ? 'is-junior' : 'is-senior';
        var href = (subject !== 'math' ? 'explore/?subject=' + subject + '&' : 'explore/?')
          + 'grade=' + group.grade;

        var link = document.createElement('a');
        link.className = 'grade-card ' + klass;
        link.href = href;
        var stage = document.createElement('span');
        stage.className = 'grade-stage';
        stage.textContent = band;
        var name = document.createElement('strong');
        name.textContent = group.label;
        var count = document.createElement('span');
        count.className = 'grade-count';
        count.textContent = group.topics.length + ' 个知识点';
        var split = document.createElement('span');
        split.className = 'grade-stage';
        split.textContent = units.size + ' 个学习单元';
        link.append(stage, name, count, split);
        grades.append(link);
      });
  }).catch(function (error) {
    fail('数据没有加载成功（' + (error && error.message ? error.message : error) + '）。请在项目根目录运行 python3 -m http.server 8000，再用浏览器打开，不要直接双击 html 文件。');
  });
})();
