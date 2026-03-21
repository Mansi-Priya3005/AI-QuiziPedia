import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Filter,
  Calendar,
  BarChart3,
  Plus
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../services/api';
import EnhancedModal from '../components/EnhancedModal';
import FixedEnhancedQuizCard from '../components/FixedEnhancedQuizCard';
import QuizHistoryCard from '../components/QuizHistoryCard';
import LoadingSpinner from '../components/LoadingSpinner';

const EnhancedHistoryTab = ({ onGenerateNewQuiz }) => {
  const [quizzes, setQuizzes] = useState([]);
  const [filteredQuizzes, setFilteredQuizzes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedQuiz, setSelectedQuiz] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [viewMode, setViewMode] = useState('list');

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    filterAndSortQuizzes();
  }, [quizzes, searchTerm, sortBy]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const history = await api.getQuizHistory();
      setQuizzes(history);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setLoading(false);
    }
  };

  const filterAndSortQuizzes = () => {
    let filtered = quizzes.filter(quiz =>
      quiz.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      quiz.url.toLowerCase().includes(searchTerm.toLowerCase())
    );

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'newest':
          return new Date(b.date_generated) - new Date(a.date_generated);
        case 'oldest':
          return new Date(a.date_generated) - new Date(b.date_generated);
        case 'title':
          return a.title.localeCompare(b.title);
        case 'attempts':
          return (b.attempts_count || 0) - (a.attempts_count || 0);
        default:
          return 0;
      }
    });

    setFilteredQuizzes(filtered);
  };

  const handleViewDetails = async (quiz) => {
    try {
      const quizDetails = await api.getQuizById(quiz.id);
      setSelectedQuiz(quizDetails);
      setViewMode('details');
      setModalOpen(true);
    } catch (err) {
      console.error('Failed to load quiz details:', err);
    }
  };

  const handleTakeQuiz = async (quiz) => {
    try {
      const quizDetails = await api.getQuizById(quiz.id);
      setSelectedQuiz(quizDetails);
      setViewMode('take');
      setModalOpen(true);
    } catch (err) {
      console.error('Failed to load quiz for taking:', err);
    }
  };

  const handleModalClose = () => {
    setModalOpen(false);
    setSelectedQuiz(null);
    setViewMode('list');
    loadHistory();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 flex items-center justify-center">
        <LoadingSpinner size="xl" text="Loading your quiz history..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Quiz <span className="gradient-text">History</span>
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Review all your previously generated quizzes and track your learning progress.
          </p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8"
        >
          {[
            { 
              label: 'Total Quizzes', 
              value: quizzes.length, 
              icon: BarChart3, 
              color: 'blue' 
            },
            { 
              label: 'Total Attempts', 
              value: quizzes.reduce((sum, q) => sum + (q.attempts_count || 0), 0), 
              icon: Calendar, 
              color: 'green' 
            },
            { 
              label: 'This Week', 
              value: quizzes.filter(q => {
                const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
                return new Date(q.date_generated) > weekAgo;
              }).length, 
              icon: Calendar, 
              color: 'amber' 
            },
            { 
              label: 'Active', 
              value: quizzes.filter(q => (q.attempts_count || 0) > 0).length, 
              icon: BarChart3, 
              color: 'purple' 
            }
          ].map((stat, index) => (
            <div key={index} className="card p-6 text-center">
              <div className={`w-12 h-12 bg-${stat.color}-100 rounded-2xl flex items-center justify-center mx-auto mb-3`}>
                <stat.icon className={`text-${stat.color}-600`} size={24} />
              </div>
              <div className="text-2xl font-bold text-gray-900 mb-1">{stat.value}</div>
              <div className="text-sm text-gray-600">{stat.label}</div>
            </div>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="card p-6 mb-8"
        >
          <div className="flex flex-col lg:flex-row gap-4 items-center justify-between">
            <div className="flex-1 w-full lg:max-w-md">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
                <input
                  type="text"
                  placeholder="Search quizzes by title or URL..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200"
                />
              </div>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Filter size={18} className="text-gray-400" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all duration-200"
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="title">Title A-Z</option>
                  <option value="attempts">Most Attempts</option>
                </select>
              </div>

              <button
                onClick={onGenerateNewQuiz}
                className="btn-primary flex items-center space-x-2"
              >
                <Plus size={18} />
                <span>New Quiz</span>
              </button>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="space-y-6"
        >
          <AnimatePresence>
            {filteredQuizzes.map((quiz, index) => (
              <QuizHistoryCard
                key={quiz.id}
                quiz={quiz}
                onViewDetails={handleViewDetails}
                onTakeQuiz={handleTakeQuiz}
              />
            ))}
          </AnimatePresence>
        </motion.div>

        {filteredQuizzes.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="card p-12 text-center"
          >
            <div className="w-24 h-24 bg-gradient-to-br from-gray-200 to-gray-300 rounded-3xl flex items-center justify-center mx-auto mb-6">
              <BarChart3 className="text-gray-400" size={40} />
            </div>
            <h3 className="text-2xl font-bold text-gray-900 mb-4">
              {quizzes.length === 0 ? 'No Quizzes Yet' : 'No Matching Quizzes'}
            </h3>
            <p className="text-gray-600 max-w-md mx-auto mb-6">
              {quizzes.length === 0 
                ? 'Your generated quizzes will appear here. Start by creating your first quiz from a Wikipedia article!'
                : 'No quizzes match your search criteria. Try adjusting your search terms.'
              }
            </p>
            <button 
              onClick={onGenerateNewQuiz}
              className="btn-primary"
            >
              Generate First Quiz
            </button>
          </motion.div>
        )}
      </div>

      <EnhancedModal
        isOpen={modalOpen}
        onClose={handleModalClose}
        title={selectedQuiz?.title}
        size="xl"
      >
        {selectedQuiz && (
          <div className="p-4">
            <FixedEnhancedQuizCard 
              quiz={selectedQuiz} 
              mode={viewMode === 'take' ? 'take' : 'view'}
              onModeChange={(newMode) => {
                if (newMode === 'view') {
                  setViewMode('details');
                }
              }}
            />
          </div>
        )}
      </EnhancedModal>
    </div>
  );
};

export default EnhancedHistoryTab;