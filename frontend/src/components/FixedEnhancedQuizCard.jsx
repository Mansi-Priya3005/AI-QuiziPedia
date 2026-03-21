import React, { useState, useEffect } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  ChevronLeft,
  CheckCircle2, 
  XCircle, 
  HelpCircle,
  Star,
  ExternalLink,
  Calendar,
  Users,
  MapPin,
  Building,
  BarChart3,
  Target,
  Clock,
  Award,
  BookOpen,
  Globe
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import FixedQuizTaker from './FixedQuizTaker';
import { api } from '../services/api';

const EntitySection = ({ entities }) => {
  if (!entities || Object.keys(entities).length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <BookOpen size={48} className="mx-auto mb-4 text-gray-300" />
        <p>No key entities extracted from this article.</p>
      </div>
    );
  }

  const icons = {
    people: Users,
    organizations: Building,
    locations: MapPin,
    concepts: Globe,
    events: Calendar
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Object.entries(entities).map(([category, items]) => {
        const Icon = icons[category] || HelpCircle;
        return (
          <div key={category} className="card p-4 hover:shadow-md transition-shadow">
            <div className="flex items-center mb-3">
              <Icon size={18} className="text-primary-600 mr-2" />
              <h4 className="font-semibold text-gray-900 capitalize">{category}</h4>
              <span className="ml-2 text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">
                {items.length}
              </span>
            </div>
            <ul className="space-y-2">
              {items.slice(0, 5).map((entity, idx) => (
                <li key={idx} className="flex items-center text-sm text-gray-600">
                  <div className="w-1.5 h-1.5 bg-primary-400 rounded-full mr-3"></div>
                  {entity}
                </li>
              ))}
              {items.length > 5 && (
                <li className="text-xs text-primary-600 font-medium mt-2">
                  +{items.length - 5} more
                </li>
              )}
            </ul>
          </div>
        );
      })}
    </div>
  );
};

const RelatedTopicsSection = ({ topics }) => {
  if (!topics || topics.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Globe size={48} className="mx-auto mb-4 text-gray-300" />
        <p>No related topics suggested for this article.</p>
      </div>
    );
  }

  return (
    <div className="card p-8">
      <h3 className="text-2xl font-bold text-gray-900 mb-6 flex items-center">
        <Globe className="mr-3 text-primary-600" size={24} />
        Continue Learning
      </h3>
      <p className="text-gray-600 mb-8 text-lg">
        Explore these related topics to deepen your understanding:
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {topics.map((topic, index) => (
          <motion.div
            key={index}
            whileHover={{ scale: 1.05, y: -5 }}
            className="bg-gradient-to-br from-white to-gray-50 border border-gray-200 rounded-2xl p-6 text-center hover:shadow-xl transition-all duration-300 cursor-pointer group"
          >
            <div className="w-16 h-16 bg-primary-100 rounded-2xl flex items-center justify-center mx-auto mb-4 group-hover:bg-primary-200 transition-colors">
              <span className="text-2xl">📚</span>
            </div>
            <h4 className="font-semibold text-gray-900 text-lg mb-2 group-hover:text-primary-600 transition-colors">
              {topic}
            </h4>
            <p className="text-gray-500 text-sm">
              Explore this topic on Wikipedia
            </p>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

const AttemptsHistory = ({ attempts, quiz, onViewAttempt }) => {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-emerald-600 bg-emerald-100';
    if (score >= 60) return 'text-amber-600 bg-amber-100';
    return 'text-rose-600 bg-rose-100';
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-gray-900 flex items-center">
        <BarChart3 size={20} className="mr-2 text-primary-600" />
        Your Attempts ({attempts.length})
      </h3>
      
      {attempts.map((attempt, index) => (
        <motion.div
          key={attempt.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.1 }}
          className="card p-4 hover:shadow-md transition-shadow cursor-pointer"
          onClick={() => onViewAttempt(attempt)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold ${getScoreColor(attempt.score)}`}>
                {Math.round(attempt.score)}%
              </div>
              <div>
                <div className="font-semibold text-gray-900">
                  {attempt.correct_answers} / {attempt.total_questions} correct
                </div>
                <div className="flex items-center space-x-4 text-sm text-gray-500">
                  <span className="flex items-center">
                    <Clock size={14} className="mr-1" />
                    {formatTime(attempt.time_taken)}
                  </span>
                  <span className="flex items-center">
                    <Calendar size={14} className="mr-1" />
                    {formatDate(attempt.date_attempted)}
                  </span>
                </div>
              </div>
            </div>
            
            <div className="text-right">
              <div className={`text-sm font-medium px-2 py-1 rounded-full ${getScoreColor(attempt.score)}`}>
                {attempt.score >= 80 ? 'Excellent' : 
                 attempt.score >= 60 ? 'Good' : 
                 'Needs Practice'}
              </div>
              {index === 0 && (
                <div className="text-xs text-primary-600 font-medium mt-1 flex items-center justify-end">
                  <Award size={12} className="mr-1" />
                  Latest
                </div>
              )}
            </div>
          </div>
        </motion.div>
      ))}

      {attempts.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          <Target size={48} className="mx-auto mb-4 text-gray-300" />
          <p>No attempts yet. Be the first to take this quiz!</p>
        </div>
      )}
    </div>
  );
};

const FixedEnhancedQuizCard = ({ quiz, mode = 'view', onModeChange }) => {
  const [activeSection, setActiveSection] = useState(mode === 'take' ? 'quiz' : 'overview');
  const [attempts, setAttempts] = useState([]);
  const [loadingAttempts, setLoadingAttempts] = useState(false);
  const [selectedAttempt, setSelectedAttempt] = useState(null);
  const [viewMode, setViewMode] = useState(mode); // 'view', 'take', 'review'

  useEffect(() => {
    if (quiz?.id) {
      loadAttempts();
    }
  }, [quiz?.id]);

  useEffect(() => {
    setViewMode(mode);
    if (mode === 'take') {
      setActiveSection('quiz');
    } else if (mode === 'view') {
      setActiveSection('overview');
    }
  }, [mode]);

  const loadAttempts = async () => {
    setLoadingAttempts(true);
    try {
      const attemptsData = await api.getQuizAttempts(quiz.id);
      setAttempts(attemptsData);
    } catch (error) {
      console.error('Failed to load attempts:', error);
      setAttempts([]);
    } finally {
      setLoadingAttempts(false);
    }
  };

  const handleQuizComplete = (result) => {
    loadAttempts();
    setSelectedAttempt(result);
    setViewMode('review');
    setActiveSection('results');
  };

  const handleViewAttempt = (attempt) => {
    setSelectedAttempt(attempt);
    setViewMode('review');
    setActiveSection('results');
  };

  const handleExitReview = () => {
    setViewMode('view');
    setActiveSection('history');
    setSelectedAttempt(null);
  };

  const handleStartQuiz = () => {
    setViewMode('take');
    setActiveSection('quiz');
    if (onModeChange) {
      onModeChange('take');
    }
  };

  const bestScore = attempts.length > 0 
    ? Math.max(...attempts.map(a => a.score))
    : null;

  const getTabs = () => {
    if (viewMode === 'take') {
      return ['quiz'];
    } else if (viewMode === 'review') {
      return ['results'];
    } else {
      return ['overview', 'history', 'topics'];
    }
  };

  const tabs = getTabs();

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="space-y-6"
    >
      {viewMode === 'view' && (
        <div className="card p-8 bg-gradient-to-br from-white to-gray-50">
          <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-3 h-8 bg-gradient-to-b from-primary-500 to-primary-600 rounded-full"></div>
                <h1 className="text-3xl font-bold text-gray-900">{quiz.title}</h1>
              </div>
              <p className="text-gray-600 text-lg leading-relaxed mb-6">{quiz.summary}</p>
              
              <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                <div className="flex items-center">
                  <Calendar size={16} className="mr-2" />
                  Generated on {new Date(quiz.date_generated || Date.now()).toLocaleDateString()}
                </div>
                <div className="flex items-center">
                  <Target size={16} className="mr-2" />
                  {quiz.quiz?.length || 0} questions
                </div>
                {bestScore && (
                  <div className="flex items-center">
                    <Award size={16} className="mr-2" />
                    Best Score: {Math.round(bestScore)}%
                  </div>
                )}
              </div>
            </div>
            
            <div className="flex flex-col gap-3">
              <a
                href={quiz.url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary flex items-center justify-center space-x-2"
              >
                <ExternalLink size={16} />
                <span>View Article</span>
              </a>
              <button
                onClick={handleStartQuiz}
                className="btn-primary flex items-center justify-center space-x-2"
              >
                <Target size={16} />
                <span>Take Quiz</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'view' && attempts.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-primary-600">{attempts.length}</div>
            <div className="text-sm text-gray-600">Total Attempts</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-emerald-600">{Math.round(bestScore)}%</div>
            <div className="text-sm text-gray-600">Best Score</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-amber-600">
              {Math.round(attempts.reduce((sum, a) => sum + a.score, 0) / attempts.length)}%
            </div>
            <div className="text-sm text-gray-600">Average Score</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-bold text-blue-600">
              {quiz.quiz?.length || 0}
            </div>
            <div className="text-sm text-gray-600">Questions</div>
          </div>
        </div>
      )}

      {loadingAttempts && (
        <div className="card p-8 text-center">
          <div className="flex flex-col items-center">
            <div className="loading-dots mb-4">
              <div></div>
              <div></div>
              <div></div>
              <div></div>
            </div>
            <p className="text-gray-600">Loading your quiz attempts...</p>
          </div>
        </div>
      )}

      {viewMode === 'view' && !loadingAttempts && (
        <div className="flex space-x-1 p-1 bg-gray-100 rounded-2xl w-fit">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveSection(tab)}
              className={`px-6 py-3 rounded-xl font-medium capitalize transition-all duration-200 ${
                activeSection === tab
                  ? 'bg-white text-primary-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab === 'history' ? `History (${attempts.length})` : tab}
            </button>
          ))}
        </div>
      )}

      {(viewMode === 'take' || viewMode === 'review') && (
        <div className="flex justify-between items-center">
          <button
            onClick={() => {
              setViewMode('view');
              setActiveSection('overview');
              setSelectedAttempt(null);
              if (onModeChange) {
                onModeChange('view');
              }
            }}
            className="btn-secondary flex items-center space-x-2"
          >
            <ChevronLeft size={18} />
            <span>Back to Overview</span>
          </button>
          
          {viewMode === 'review' && selectedAttempt && (
            <div className="text-lg font-semibold text-gray-900">
              Attempt Score: {Math.round(selectedAttempt.score)}%
            </div>
          )}
        </div>
      )}

      <AnimatePresence mode="wait">
        {activeSection === 'overview' && viewMode === 'view' && !loadingAttempts && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
            className="space-y-6"
          >
            <div className="card p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center">
                <Users className="mr-3 text-primary-600" size={24} />
                Key Entities
              </h3>
              <EntitySection entities={quiz.key_entities || {}} />
            </div>

            {quiz.sections && quiz.sections.length > 0 && (
              <div className="card p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center">
                  <BookOpen className="mr-3 text-primary-600" size={24} />
                  Article Sections
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {quiz.sections.map((section, index) => (
                    <div
                      key={index}
                      className="bg-gradient-to-r from-gray-50 to-white border border-gray-200 rounded-xl p-4 text-center hover:shadow-md transition-shadow"
                    >
                      <div className="w-8 h-8 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center text-sm font-bold mx-auto mb-2">
                        {index + 1}
                      </div>
                      <span className="font-medium text-gray-900">{section}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {attempts.length > 0 && (
              <div className="card p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Award className="mr-2 text-blue-600" size={20} />
                  Latest Attempt
                </h3>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-blue-600">
                      {Math.round(attempts[0].score)}%
                    </div>
                    <div className="text-sm text-gray-600">
                      {attempts[0].correct_answers} / {attempts[0].total_questions} correct
                    </div>
                  </div>
                  <button
                    onClick={() => setActiveSection('history')}
                    className="btn-secondary"
                  >
                    View All Attempts
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {(activeSection === 'quiz' || viewMode === 'take') && (
          <motion.div
            key="quiz"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <FixedQuizTaker 
              quiz={quiz} 
              onQuizComplete={handleQuizComplete}
              onExit={handleExitReview}
            />
          </motion.div>
        )}

        {activeSection === 'history' && viewMode === 'view' && !loadingAttempts && (
          <motion.div
            key="history"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <AttemptsHistory 
              attempts={attempts} 
              quiz={quiz}
              onViewAttempt={handleViewAttempt}
            />
          </motion.div>
        )}

        {activeSection === 'topics' && viewMode === 'view' && !loadingAttempts && (
          <motion.div
            key="topics"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <RelatedTopicsSection topics={quiz.related_topics || []} />
          </motion.div>
        )}

        {(activeSection === 'results' || viewMode === 'review') && selectedAttempt && (
          <motion.div
            key="results"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <FixedQuizTaker 
              quiz={quiz} 
              showResults={true}
              attemptData={selectedAttempt}
              onExit={handleExitReview}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default FixedEnhancedQuizCard;