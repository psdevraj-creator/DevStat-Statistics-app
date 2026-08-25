/* ── RADIOBIOLOGY — Core Interactive Functions ── */

document.addEventListener('DOMContentLoaded', function() {
  initTabs();
  initAccordions();
  initRecallQuestions();
  initMCQs();
  initGlossaryTooltips();
  loadProgress();
});

/* ── TAB SWITCHER ── */
function initTabs() {
  document.querySelectorAll('.tab-container').forEach(function(container) {
    var tabs = container.querySelectorAll('.tab');
    var contentDiv = container.nextElementSibling;
    if (!contentDiv || !contentDiv.classList.contains('tab-contents')) {
      return;
    }
    tabs.forEach(function(tab) {
      tab.addEventListener('click', function() {
        var target = tab.getAttribute('data-tab');
        container.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        contentDiv.querySelectorAll('.tab-content').forEach(function(tc) { tc.classList.remove('active'); });
        var targetEl = contentDiv.querySelector('#tab-' + target);
        if (targetEl) targetEl.classList.add('active');
      });
    });
  });
}

/* ── ACCORDION ── */
function initAccordions() {
  document.querySelectorAll('.accordion-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      btn.classList.toggle('open');
      var panel = btn.nextElementSibling;
      if (panel) {
        panel.classList.toggle('open');
        if (panel.classList.contains('open')) {
          panel.style.maxHeight = panel.scrollHeight + 'px';
        } else {
          panel.style.maxHeight = '0';
        }
      }
    });
  });
}

/* ── RECALL QUESTIONS (click to reveal answer) ── */
function initRecallQuestions() {
  document.querySelectorAll('.recall-item').forEach(function(item) {
    item.addEventListener('click', function() {
      item.classList.toggle('open');
      var answer = item.querySelector('.a');
      if (answer) {
        answer.classList.toggle('show');
      }
    });
  });
}

/* ── MCQ MINI-QUIZ ── */
function initMCQs() {
  document.querySelectorAll('.mcq-option').forEach(function(opt) {
    opt.addEventListener('click', function() {
      var parent = opt.closest('.mcq-item');
      var isRadio = opt.querySelector('input[type="radio"]');
      if (isRadio) {
        parent.querySelectorAll('.mcq-option').forEach(function(o) { o.classList.remove('selected'); });
        opt.classList.add('selected');
      } else {
        opt.classList.toggle('selected');
      }
    });
  });

  document.querySelectorAll('.mcq-submit').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var parent = btn.closest('.mcq-item');
      var selected = parent.querySelector('.mcq-option.selected');
      var feedback = parent.querySelector('.mcq-feedback');
      if (!selected || !feedback) return;
      var value = selected.getAttribute('data-value') || (selected.querySelector('input') ? selected.querySelector('input').value : '');
      var correct = parent.getAttribute('data-correct');
      if (value === correct) {
        selected.classList.add('correct');
        feedback.className = 'mcq-feedback show correct';
        feedback.textContent = parent.getAttribute('data-correct-explanation') || '✓ Correct!';
      } else {
        selected.classList.add('wrong');
        feedback.className = 'mcq-feedback show incorrect';
        var correctOpt = parent.querySelector('.mcq-option[data-value="' + correct + '"]');
        if (correctOpt) correctOpt.classList.add('correct');
        feedback.textContent = parent.getAttribute('data-correct-explanation') || '✗ Incorrect. See explanation below.';
      }
      btn.disabled = true;
      btn.style.opacity = '0.5';
      // Track progress
      var topicId = parent.closest('[data-topic]') ? parent.closest('[data-topic]').getAttribute('data-topic') : 'unknown';
      updateProgress(topicId, 'mcq_' + parent.getAttribute('data-id'));
    });
  });
}

/* ── GLOSSARY TOOLTIPS ── */
function initGlossaryTooltips() {
  document.querySelectorAll('.glossary-term').forEach(function(el) {
    var def = el.getAttribute('data-def');
    if (def) {
      el.setAttribute('title', def);
    }
  });
}

/* ── PROGRESS TRACKING (localStorage) ── */
function updateProgress(topicId, section) {
  var key = 'radbio_progress_' + topicId;
  var data = {};
  try {
    data = JSON.parse(localStorage.getItem(key)) || {};
  } catch(e) { data = {}; }
  data[section] = true;
  localStorage.setItem(key, JSON.stringify(data));
  updateProgressDisplay();
}

function getTopicProgress(topicId) {
  var key = 'radbio_progress_' + topicId;
  try {
    var data = JSON.parse(localStorage.getItem(key)) || {};
    return data;
  } catch(e) { return {}; }
}

function loadProgress() {
  updateProgressDisplay();
}

function updateProgressDisplay() {
  document.querySelectorAll('[data-topic-progress]').forEach(function(el) {
    var topicId = el.getAttribute('data-topic-progress');
    var data = getTopicProgress(topicId);
    var count = Object.keys(data).length;
    el.textContent = count + ' completed';
  });
}

/* ── FLASHCARD MODE (for question bank) ── */
function initFlashcardMode(questions) {
  var container = document.querySelector('.flashcard-container');
  var card = container ? container.querySelector('.flashcard') : null;
  var counter = container ? container.querySelector('.flashcard-counter') : null;
  var prevBtn = container ? container.querySelector('.fc-prev') : null;
  var nextBtn = container ? container.querySelector('.fc-next') : null;
  if (!card || !container) return;

  var currentIndex = 0;
  var fcQuestions = questions.filter(function(q) { return q.subtype === 'flashcard' || true; });

  function showCard(index) {
    if (fcQuestions.length === 0) {
      card.querySelector('.fc-stem').textContent = 'No flashcards available.';
      return;
    }
    var q = fcQuestions[index % fcQuestions.length];
    card.classList.remove('flipped');
    card.querySelector('.fc-stem').textContent = q.stem;
    card.querySelector('.fc-answer').textContent = q.correct_answer;
    card.querySelector('.fc-explain').textContent = q.explanation || '';
    if (counter) counter.textContent = (index + 1) + ' of ' + fcQuestions.length;
  }

  card.addEventListener('click', function() {
    card.classList.toggle('flipped');
  });

  if (prevBtn) prevBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    currentIndex = (currentIndex - 1 + fcQuestions.length) % fcQuestions.length;
    showCard(currentIndex);
  });

  if (nextBtn) nextBtn.addEventListener('click', function(e) {
    e.stopPropagation();
    currentIndex = (currentIndex + 1) % fcQuestions.length;
    showCard(currentIndex);
  });

  showCard(0);
}
