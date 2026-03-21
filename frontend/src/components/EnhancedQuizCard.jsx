import React, { useState, useEffect } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
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
  Award
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import QuizTaker from './QuizTaker';
import { api } from '../services/api';

const AttemptsHistory = ({ attempts, quiz }) => {
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
          className="card p-4 hover:shadow-md transition-shadow"
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

const EnhancedQuizCard = ({ quiz, showAnswers = true, mode = 'view' }) => {
  const [activeSection, setActiveSection] = useState(mode === 'take' ? 'quiz' : 'overview');
  const [attempts, setAttempts] = useState([]);
  const [loadingAttempts, setLoadingAttempts] = useState(false);
  const [latestAttempt, setLatestAttempt] = useState(null);

  useEffect(() => {
    if (quiz?.id) {
      loadAttempts();
    }
  }, [quiz?.id]);

  const loadAttempts = async () => {
    setLoadingAttempts(true);
    try {
      const attemptsData = await api.getQuizAttempts(quiz.id);
      setAttempts(attemptsData);
      if (attemptsData.length > 0) {
        setLatestAttempt(attemptsData[0]);
      }
    } catch (error) {
      console.error('Failed to load attempts:', error);
    } finally {
      setLoadingAttempts(false);
    }
  };

  const handleQuizComplete = (result) => {
    setLatestAttempt(result);
    loadAttempts();
    setActiveSection('results');
  };

  const bestScore = attempts.length > 0 
    ? Math.max(...attempts.map(a => a.score))
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      className="space-y-6"
    >
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
                Generated on {new Date().toLocaleDateString()}
              </div>
              <div className="flex items-center">
                <Target size={16} className="mr-2" />
                {quiz.quiz.length} questions
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
            {mode !== 'take' && (
              <button
                onClick={() => setActiveSection('quiz')}
                className="btn-primary flex items-center justify-center space-x-2"
              >
                <Target size={16} />
                <span>Take Quiz</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {attempts.length > 0 && (
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
              {quiz.quiz.length}
            </div>
            <div className="text-sm text-gray-600">Questions</div>
          </div>
        </div>
      )}

      <div className="flex space-x-1 p-1 bg-gray-100 rounded-2xl w-fit">
        {['overview', 'quiz', 'history', 'topics'].map((tab) => (
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

      <AnimatePresence mode="wait">
        {activeSection === 'overview' && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <div className="card p-6 mb-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center">
                <Users className="mr-3 text-primary-600" size={24} />
                Key Entities
              </h3>
            </div>

            {latestAttempt && (
              <div className="card p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-200 mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  <Award className="mr-2 text-blue-600" size={20} />
                  Latest Attempt
                </h3>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-2xl font-bold text-blue-600">
                      {Math.round(latestAttempt.score)}%
                    </div>
                    <div className="text-sm text-gray-600">
                      {latestAttempt.correct_answers} / {latestAttempt.total_questions} correct
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

        {activeSection === 'quiz' && (
          <motion.div
            key="quiz"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <QuizTaker 
              quiz={quiz} 
              onQuizComplete={handleQuizComplete}
            />
          </motion.div>
        )}

        {activeSection === 'history' && (
          <motion.div
            key="history"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <AttemptsHistory attempts={attempts} quiz={quiz} />
          </motion.div>
        )}

        {activeSection === 'results' && latestAttempt && (
          <motion.div
            key="results"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3 }}
          >
            <QuizTaker 
              quiz={quiz} 
              showResults={true}
              attemptData={latestAttempt}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default EnhancedQuizCard;