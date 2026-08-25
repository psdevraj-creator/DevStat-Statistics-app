/* ── QUESTION BANK ENGINE ── */
/* Handles loading, filtering, rendering, flashcard mode, and self-test mode */

var QB = {};

QB.questions = [];
QB.filteredQuestions = [];
QB.currentFilters = { topic: 'all', difficulty: 'all', type: 'all', search: '' };
QB.flashcardMode = false;
QB.selfTestMode = false;
QB.selfTestAnswers = {};

  QB.init = async function() {
    var self = this;
    
    try {
      const data = await DataLoader.load('data/questions.json');
      self.questions = data.questions || [];
      self.filteredQuestions = self.questions.slice();
      self.renderStats();
      self.renderFilters();
      self.renderQuestions();
      self.initFilterListeners();
      self.initFlashcardToggle();
      self.initSelfTestToggle();
    } catch (err) {
      console.error('Failed to load questions:', err);
      document.getElementById('question-list').innerHTML =
        '<div class="info-card"><p style="color:#991b1b;">⚠️ Failed to load question bank. Please ensure data/questions.json exists.</p></div>';
    }
  };


QB.renderStats = function() {
  var el = document.getElementById('qb-stats');
  if (!el) return;
  var total = this.questions.length;
  var topics = {};
  this.questions.forEach(function(q) { topics[q.topic] = (topics[q.topic] || 0) + 1; });
  var topicCount = Object.keys(topics).length;
  el.innerHTML =
    '<div class="qb-stat">Total Questions: <strong>' + total + '</strong></div>' +
    '<div class="qb-stat">Topics: <strong>' + topicCount + '</strong></div>' +
    '<div class="qb-stat">Showing: <strong>' + this.filteredQuestions.length + '</strong></div>';
};

QB.renderFilters = function() {
  var container = document.getElementById('filter-container');
  if (!container) return;
  // Get unique topics
  var topics = {};
  this.questions.forEach(function(q) { topics[q.topic] = true; });
  var topicList = Object.keys(topics).sort();
  var topicOpts = '';
  topicList.forEach(function(t) { topicOpts += '<option value="' + t + '">' + t + '</option>'; });

  container.innerHTML =
    '<input type="text" id="search-input" placeholder="Search questions..." />' +
    '<select id="topic-filter"><option value="all">All Topics</option>' + topicOpts + '</select>' +
    '<select id="difficulty-filter">' +
      '<option value="all">All Difficulties</option>' +
      '<option value="easy">Easy</option>' +
      '<option value="standard">Standard</option>' +
      '<option value="hard">Hard</option>' +
    '</select>' +
    '<select id="type-filter">' +
      '<option value="all">All Types</option>' +
      '<option value="mcq">MCQ</option>' +
      '<option value="short-answer">Short Answer</option>' +
      '<option value="flashcard">Flashcard</option>' +
    '</select>';
};

QB.initFilterListeners = function() {
  var self = this;
  function applyFilters() {
    self.currentFilters.topic = document.getElementById('topic-filter').value;
    self.currentFilters.difficulty = document.getElementById('difficulty-filter').value;
    self.currentFilters.type = document.getElementById('type-filter').value;
    self.currentFilters.search = document.getElementById('search-input').value.toLowerCase();
    self.applyFilter();
  }

  document.getElementById('topic-filter').addEventListener('change', applyFilters);
  document.getElementById('difficulty-filter').addEventListener('change', applyFilters);
  document.getElementById('type-filter').addEventListener('change', applyFilters);
  document.getElementById('search-input').addEventListener('input', function() {
    clearTimeout(self._searchTimeout);
    self._searchTimeout = setTimeout(applyFilters, 300);
  });
};

QB.applyFilter = function() {
  var self = this;
  var f = this.currentFilters;
  this.filteredQuestions = this.questions.filter(function(q) {
    if (f.topic !== 'all' && q.topic !== f.topic) return false;
    if (f.difficulty !== 'all' && q.difficulty !== f.difficulty) return false;
    if (f.type !== 'all' && q.subtype !== f.type) return false;
    if (f.search) {
      var text = (q.stem + ' ' + (q.explanation || '') + ' ' + (q.correct_answer || '')).toLowerCase();
      if (text.indexOf(f.search) === -1) return false;
    }
    return true;
  });
  this.renderStats();
  this.renderQuestions();
};

QB.renderQuestions = function() {
  var el = document.getElementById('question-list');
  if (!el) return;
  var self = this;
  var html = '';

  if (this.filteredQuestions.length === 0) {
    html = '<div class="info-card"><p style="text-align:center;color:#94a3b8;">No questions match your filters. Try broadening your search.</p></div>';
    el.innerHTML = html;
    return;
  }

  this.filteredQuestions.forEach(function(q, idx) {
    var topicLabel = q.topic || 'general';
    html += '<div class="q-card" data-q-id="' + q.id + '">';
    html += '<div class="q-meta">';
    html += '<span class="q-tag ' + (q.difficulty || 'standard') + '">' + (q.difficulty || 'standard') + '</span>';
    html += '<span class="q-tag ' + (q.subtype || 'mcq') + '">' + (q.subtype || 'mcq') + '</span>';
    html += '<span class="q-tag" style="background:#f1f5f9;color:#475569;">' + topicLabel + '</span>';
    html += '</div>';
    html += '<div class="q-stem">' + q.stem + '</div>';

    if (q.subtype === 'mcq' && q.options) {
      html += '<div class="q-options" data-q-idx="' + idx + '">';
      q.options.forEach(function(opt, oi) {
        var letter = String.fromCharCode(65 + oi);
        html += '<label><input type="radio" name="q_' + idx + '" value="' + letter + '" /> ' + letter + '. ' + opt + '</label>';
      });
      html += '</div>';
    }

    if (q.subtype === 'mcq') {
      html += '<button class="q-reveal-btn" onclick="QB.revealAnswer(' + idx + ')">Show Answer</button>';
    } else {
      html += '<button class="q-reveal-btn" onclick="QB.revealAnswer(' + idx + ')">Reveal</button>';
    }

    html += '<div class="q-answer" id="q-answer-' + idx + '">';
    html += '<div class="ans-label">✓ Answer: ' + (q.correct_answer || '') + '</div>';
    html += '<div class="ans-explain">' + (q.explanation || '') + '</div>';
    if (q.related_concepts) {
      html += '<div style="margin-top:6px;font-size:0.78rem;color:#94a3b8;">Related: ' + q.related_concepts.join(', ') + '</div>';
    }
    if (q.source_topic_reference) {
      html += '<div style="font-size:0.75rem;color:#94a3b8;margin-top:4px;">Source: ' + q.source_topic_reference + '</div>';
    }
    html += '</div></div>';
  });

  el.innerHTML = html;
};

QB.revealAnswer = function(idx) {
  var el = document.getElementById('q-answer-' + idx);
  if (el) {
    el.classList.toggle('show');
  }
  // If MCQ, highlight correct answer
  if (this.filteredQuestions[idx] && this.filteredQuestions[idx].subtype === 'mcq') {
    var radios = document.querySelectorAll('.q-options[data-q-idx="' + idx + '"] input[type="radio"]');
    var correct = this.filteredQuestions[idx].correct_answer;
    radios.forEach(function(r) {
      r.disabled = true;
    });
  }
};

QB.initFlashcardToggle = function() {
  var btn = document.getElementById('flashcard-toggle');
  if (!btn) return;
  var self = this;
  btn.addEventListener('click', function() {
    var container = document.querySelector('.flashcard-container');
    if (!container) return;
    if (container.classList.contains('active')) {
      container.classList.remove('active');
      btn.textContent = '📇 Flashcard Mode';
      return;
    }
    container.classList.add('active');
    btn.textContent = '📇 Exit Flashcard Mode';
    // Initialize flashcard with current filtered questions
    if (typeof initFlashcardMode === 'function') {
      initFlashcardMode(self.filteredQuestions);
    }
  });
};

QB.initSelfTestToggle = function() {
  var btn = document.getElementById('self-test-toggle');
  if (!btn) return;
  var self = this;
  btn.addEventListener('click', function() {
    if (self.selfTestMode) {
      self.selfTestMode = false;
      btn.textContent = '✍️ Self-Test Mode';
      self.renderQuestions();
      return;
    }
    self.selfTestMode = true;
    btn.textContent = '✍️ Exit Self-Test';
    self.renderSelfTest();
  });
};

QB.renderSelfTest = function() {
  var el = document.getElementById('question-list');
  if (!el) return;
  var self = this;
  var html = '';

  // Take first 10 or all if less
  var testQs = this.filteredQuestions.slice(0, Math.min(10, this.filteredQuestions.length));
  this.selfTestAnswers = {};

  html += '<div class="info-card" style="background:#f0fdf4;border-color:#a7f3d0;margin-bottom:18px;">';
  html += '<h3 style="color:#065f46;">📝 Self-Test Mode</h3>';
  html += '<p style="font-size:0.88rem;">Answer the questions below, then click "Submit All" to check your answers. You have ' + testQs.length + ' questions.</p>';
  html += '</div>';

  testQs.forEach(function(q, idx) {
    html += '<div class="q-card" data-q-id="' + q.id + '">';
    html += '<div class="q-meta">';
    html += '<span class="q-tag ' + (q.difficulty || 'standard') + '">' + (q.difficulty || 'standard') + '</span>';
    html += '<span class="q-tag ' + (q.subtype || 'mcq') + '">' + (q.subtype || 'mcq') + '</span>';
    html += '</div>';
    html += '<div class="q-stem">' + (idx + 1) + '. ' + q.stem + '</div>';

    if (q.subtype === 'mcq' && q.options) {
      html += '<div class="q-options" data-st-idx="' + idx + '">';
      q.options.forEach(function(opt, oi) {
        var letter = String.fromCharCode(65 + oi);
        html += '<label><input type="radio" name="st_q_' + idx + '" value="' + letter + '" /> ' + letter + '. ' + opt + '</label>';
      });
      html += '</div>';
    } else {
      html += '<div style="margin-top:8px;"><input type="text" class="st-input" data-st-idx="' + idx + '" placeholder="Type your answer..." style="width:100%;padding:10px 14px;border:1px solid #e2e8f0;border-radius:8px;font-size:0.88rem;" /></div>';
    }

    html += '<div class="q-answer" id="st-answer-' + idx + '">';
    html += '<div class="ans-label">✓ Answer: ' + (q.correct_answer || '') + '</div>';
    html += '<div class="ans-explain">' + (q.explanation || '') + '</div>';
    html += '</div></div>';
  });

  html += '<div style="text-align:center;margin-top:18px;">';
  html += '<button class="flashcard-mode-btn" onclick="QB.submitSelfTest()">✅ Submit All Answers</button>';
  html += '</div>';

  el.innerHTML = html;
};

QB.submitSelfTest = function() {
  var correct = 0;
  var total = 0;
  var testQs = this.filteredQuestions.slice(0, Math.min(10, this.filteredQuestions.length));

  testQs.forEach(function(q, idx) {
    var answerEl = document.getElementById('st-answer-' + idx);
    if (answerEl) answerEl.classList.add('show');

    if (q.subtype === 'mcq') {
      var selected = document.querySelector('input[name="st_q_' + idx + '"]:checked');
      if (selected) {
        total++;
        if (selected.value === q.correct_answer) correct++;
      }
    } else {
      var input = document.querySelector('.st-input[data-st-idx="' + idx + '"]');
      if (input && input.value.trim().toLowerCase() === q.correct_answer.toLowerCase()) {
        correct++;
      }
      total++;
    }
  });

  var pct = Math.round((correct / total) * 100);
  var scoreEl = document.createElement('div');
  scoreEl.className = 'info-card';
  scoreEl.style.cssText = 'text-align:center;background:#f0fdf4;border-color:#10b981;margin-top:18px;';
  scoreEl.innerHTML = '<h3 style="color:#065f46;">📊 Your Score</h3><p style="font-size:1.2rem;font-weight:700;color:#0d9488;">' + correct + ' / ' + total + ' (' + pct + '%)</p>';
  document.getElementById('question-list').appendChild(scoreEl);
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
};

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  if (document.getElementById('question-list')) {
    QB.init();
  }
});
