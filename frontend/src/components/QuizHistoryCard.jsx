import React from 'react';
import { 
  Calendar, 
  ExternalLink, 
  BarChart3,
  Target,
  Award,
  Clock
} from 'lucide-react';
import { motion } from 'framer-motion';

const QuizHistoryCard = ({ quiz, onViewDetails, onTakeQuiz }) => {
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="card p-6 hover:shadow-lg transition-all duration-300 group"
    >
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-start justify-between mb-3">
            <h3 className="text-xl font-bold text-gray-900 group-hover:text-primary-600 transition-colors line-clamp-2">
              {quiz.title}
            </h3>
            <div className="flex items-center space-x-2 ml-4 flex-shrink-0">
              <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center text-white font-bold text-sm">
                Q
              </div>
            </div>
          </div>
          
          <p className="text-gray-600 text-sm mb-4 line-clamp-2">
            {quiz.url}
          </p>
          
          <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500">
            <div className="flex items-center">
              <Calendar size={14} className="mr-1" />
              {formatDate(quiz.date_generated)}
            </div>
            <div className="flex items-center">
              <Target size={14} className="mr-1" />
              {quiz.attempts_count || 0} attempts
            </div>
            {quiz.best_score && (
              <div className="flex items-center">
                <Award size={14} className="mr-1" />
                Best: {Math.round(quiz.best_score)}%
              </div>
            )}
          </div>
        </div>
        
        <div className="flex flex-col gap-2 lg:items-end">
          <div className="flex gap-2">
            <button
              onClick={() => onViewDetails(quiz)}
              className="btn-secondary flex items-center space-x-2 text-sm px-4 py-2"
            >
              <BarChart3 size={16} />
              <span>Details</span>
            </button>
            <button
              onClick={() => onTakeQuiz(quiz)}
              className="btn-primary flex items-center space-x-2 text-sm px-4 py-2"
            >
              <Target size={16} />
              <span>Take Quiz</span>
            </button>
          </div>
          
          <a
            href={quiz.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1 text-xs text-gray-500 hover:text-primary-600 transition-colors"
          >
            <ExternalLink size={12} />
            <span>View Article</span>
          </a>
        </div>
      </div>
    </motion.div>
  );
};

export default QuizHistoryCard;