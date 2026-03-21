import React, { useState, useEffect, useRef } from 'react';
import { 
  Clock, 
  CheckCircle2, 
  XCircle, 
  Award, 
  RotateCcw,
  BarChart3,
  Target,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../services/api';

const FixedQuizTaker = ({ quiz, onQuizComplete, showResults = false, attemptData = null, onExit }) => {
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [userAnswers, setUserAnswers] = useState([]);
  const [timeElapsed, setTimeElapsed] = useState(0);
  const [quizCompleted, setQuizCompleted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const timerRef = useRef(null);

  useEffect(() => {
    if (showResults && attemptData) {
      setUserAnswers(attemptData.answers || []);
      setQuizCompleted(true);
      setTimeElapsed(attemptData.time_taken || 0);
    } else {
      setCurrentQuestion(0);
      setUserAnswers([]);
      setTimeElapsed(0);
      setQuizCompleted(false);
    }
  }, [showResults, attemptData]);

  useEffect(() => {
    if (!quizCompleted && !showResults) {
      timerRef.current = setInterval(() => {
        setTimeElapsed(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [quizCompleted, showResults]);

  const handleAnswerSelect = (answer) => {
    if (quizCompleted || showResults) return;
    
    const newAnswers = [...userAnswers];
    newAnswers[currentQuestion] = answer;
    setUserAnswers(newAnswers);
  };

  const handleNext = () => {
    if (currentQuestion < quiz.quiz.length - 1) {
      setCurrentQuestion(prev => prev + 1);
    } else if (!quizCompleted) {
      handleSubmit();
    }
  };

  const handlePrevious = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1);
    }
  };

  const handleSubmit = async () => {
    if (quizCompleted) return;
    
    setSubmitting(true);
    try {
      const result = await api.submitQuizAttempt(quiz.id, {
        answers: userAnswers,
        time_taken: timeElapsed
      });
      
      setQuizCompleted(true);
      if (onQuizComplete) {
        onQuizComplete(result);
      }
    } catch (error) {
      console.error('Failed to submit quiz:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const isAnswerCorrect = (userAnswer, correctAnswer, options = []) => {
    if (!userAnswer || !correctAnswer) return false;
    
    if (/^[A-D]$/i.test(correctAnswer.trim())) {
      const userAnswerLetter = userAnswer.charAt(0).toUpperCase();
      return userAnswerLetter === correctAnswer.trim().toUpperCase();
    }
    
    return userAnswer === correctAnswer;
  };

  const calculateScore = () => {
    let correct = 0;
    quiz.quiz.forEach((question, index) => {
      if (isAnswerCorrect(userAnswers[index], question.answer, question.options)) {
        correct++;
      }
    });
    return {
      correct,
      total: quiz.quiz.length,
      percentage: Math.round((correct / quiz.quiz.length) * 100)
    };
  };

  const findCorrectOption = (question) => {
    const correctAnswer = question.answer;
    
    if (/^[A-D]$/i.test(correctAnswer.trim())) {
      const letter = correctAnswer.trim().toUpperCase();
      const optionIndex = letter.charCodeAt(0) - 65; // A=0, B=1, C=2, D=3
      if (question.options && question.options[optionIndex]) {
        return question.options[optionIndex];
      }
    }
    
    return correctAnswer;
  };

  const score = calculateScore();
  const currentQ = quiz.quiz[currentQuestion];

  if (quizCompleted || showResults) {
    return (
      <QuizResults 
        quiz={quiz}
        userAnswers={userAnswers}
        score={score}
        timeElapsed={timeElapsed}
        onRetry={() => {
          setCurrentQuestion(0);
          setUserAnswers([]);
          setTimeElapsed(0);
          setQuizCompleted(false);
        }}
        onExit={onExit}
        showResults={showResults}
      />
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="card p-6 mb-6 bg-gradient-to-r from-primary-50 to-blue-50 border-primary-200">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">{quiz.title}</h2>
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <div className="flex items-center">
                <Target size={16} className="mr-1" />
                Question {currentQuestion + 1} of {quiz.quiz.length}
              </div>
              <div className="flex items-center">
                <Clock size={16} className="mr-1" />
                {Math.floor(timeElapsed / 60)}:{(timeElapsed % 60).toString().padStart(2, '0')}
              </div>
            </div>
          </div>
          
          <div className="lg:w-48">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-primary-500 h-2 rounded-full transition-all duration-300"
                style={{ width: `${((currentQuestion + 1) / quiz.quiz.length) * 100}%` }}
              ></div>
            </div>
            <p className="text-xs text-gray-600 mt-1 text-center">
              {currentQuestion + 1} / {quiz.quiz.length}
            </p>
          </div>
        </div>
      </div>

      <motion.div
        key={currentQuestion}
        initial={{ opacity: 0, x: 50 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -50 }}
        className="card p-8 mb-6"
      >
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <div className="flex items-center space-x-3 mb-3">
              <div className="w-10 h-10 bg-primary-500 text-white rounded-xl flex items-center justify-center font-bold text-lg">
                {currentQuestion + 1}
              </div>
              <div>
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  currentQ.difficulty === 'easy' ? 'bg-emerald-100 text-emerald-800' :
                  currentQ.difficulty === 'medium' ? 'bg-amber-100 text-amber-800' :
                  'bg-rose-100 text-rose-800'
                }`}>
                  {currentQ.difficulty}
                </span>
              </div>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 leading-relaxed">
              {currentQ.question}
            </h3>
          </div>
        </div>

        <div className="space-y-3">
          {currentQ.options.map((option, index) => {
            const isSelected = userAnswers[currentQuestion] === option;
            const letter = String.fromCharCode(65 + index);
            
            return (
              <motion.div
                key={index}
                whileHover={{ scale: !quizCompleted ? 1.02 : 1 }}
                whileTap={{ scale: !quizCompleted ? 0.98 : 1 }}
                className={`p-4 rounded-xl border-2 cursor-pointer transition-all duration-200 ${
                  isSelected
                    ? 'bg-primary-50 border-primary-500 text-primary-900 shadow-md'
                    : 'bg-gray-50 border-gray-200 hover:border-primary-300 hover:bg-primary-25'
                } ${quizCompleted ? 'cursor-default' : ''}`}
                onClick={() => handleAnswerSelect(option)}
              >
                <div className="flex items-center">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center mr-4 font-semibold ${
                    isSelected
                      ? 'bg-primary-500 text-white'
                      : 'bg-gray-200 text-gray-700'
                  }`}>
                    {letter}
                  </div>
                  <span className="font-medium text-gray-900">{option}</span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.div>

      <div className="flex justify-between items-center">
        <button
          onClick={handlePrevious}
          disabled={currentQuestion === 0}
          className="btn-secondary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ChevronLeft size={18} />
          <span>Previous</span>
        </button>
        
        <div className="flex items-center space-x-3">
          {userAnswers[currentQuestion] && (
            <span className="text-sm text-green-600 font-medium flex items-center">
              <CheckCircle2 size={16} className="mr-1" />
              Answer Selected
            </span>
          )}
          
          <button
            onClick={currentQuestion === quiz.quiz.length - 1 ? handleSubmit : handleNext}
            disabled={!userAnswers[currentQuestion] || submitting}
            className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                <span>Submitting...</span>
              </>
            ) : currentQuestion === quiz.quiz.length - 1 ? (
              <>
                <CheckCircle2 size={18} />
                <span>Submit Quiz</span>
              </>
            ) : (
              <>
                <span>Next Question</span>
                <ChevronRight size={18} />
              </>
            )}
          </button>
        </div>
      </div>

      <div className="flex justify-center space-x-2 mt-8">
        {quiz.quiz.map((_, index) => (
          <button
            key={index}
            onClick={() => setCurrentQuestion(index)}
            disabled={quizCompleted}
            className={`w-3 h-3 rounded-full transition-all ${
              index === currentQuestion
                ? 'bg-primary-500 scale-125'
                : userAnswers[index]
                ? 'bg-green-500'
                : 'bg-gray-300'
            } ${quizCompleted ? 'cursor-default' : 'cursor-pointer'}`}
          />
        ))}
      </div>
    </div>
  );
};

const QuizResults = ({ quiz, userAnswers, score, timeElapsed, onRetry, onExit, showResults = false }) => {
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const isAnswerCorrect = (userAnswer, correctAnswer, options = []) => {
    if (!userAnswer || !correctAnswer) return false;
    
    if (/^[A-D]$/i.test(correctAnswer.trim())) {
      const userAnswerLetter = userAnswer.charAt(0).toUpperCase();
      return userAnswerLetter === correctAnswer.trim().toUpperCase();
    }
    
    return userAnswer === correctAnswer;
  };

  const findCorrectOption = (question) => {
    const correctAnswer = question.answer;
    
    if (/^[A-D]$/i.test(correctAnswer.trim())) {
      const letter = correctAnswer.trim().toUpperCase();
      const optionIndex = letter.charCodeAt(0) - 65; // A=0, B=1, C=2, D=3
      if (question.options && question.options[optionIndex]) {
        return question.options[optionIndex];
      }
    }
    
    return correctAnswer;
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="max-w-6xl mx-auto"
    >
      <div className="card p-8 mb-8 bg-gradient-to-br from-emerald-50 to-green-100 border-emerald-200">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: "spring", stiffness: 200 }}
          className="w-20 h-20 bg-emerald-500 rounded-full flex items-center justify-center mx-auto mb-6"
        >
          {score.percentage >= 80 ? (
            <Award size={40} className="text-white" />
          ) : score.percentage >= 60 ? (
            <CheckCircle2 size={40} className="text-white" />
          ) : (
            <BarChart3 size={40} className="text-white" />
          )}
        </motion.div>
        
        <h2 className="text-3xl font-bold text-gray-900 mb-4">
          {score.percentage >= 80 ? 'Excellent! 🎉' : 
           score.percentage >= 60 ? 'Good Job! 👍' : 
           'Keep Learning! 📚'}
        </h2>
        
        <div className="text-6xl font-bold text-emerald-600 mb-4">
          {score.percentage}%
        </div>
        
        <p className="text-gray-600 text-lg mb-6">
          You got {score.correct} out of {score.total} questions correct
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-md mx-auto mb-6">
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-2xl font-bold text-emerald-600">{score.correct}</div>
            <div className="text-sm text-gray-600">Correct</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-2xl font-bold text-rose-600">{score.total - score.correct}</div>
            <div className="text-sm text-gray-600">Incorrect</div>
          </div>
          <div className="bg-white rounded-xl p-4 shadow-sm">
            <div className="text-2xl font-bold text-primary-600">{formatTime(timeElapsed)}</div>
            <div className="text-sm text-gray-600">Time</div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          {!showResults && (
            <button onClick={onRetry} className="btn-primary flex items-center space-x-2">
              <RotateCcw size={18} />
              <span>Try Again</span>
            </button>
          )}
          {onExit && (
            <button onClick={onExit} className="btn-secondary">
              Back to Overview
            </button>
          )}
        </div>
      </div>

      <div className="card p-6 mb-6">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center">
          <BarChart3 size={24} className="mr-3 text-primary-600" />
          Question Review
        </h3>
        <div className="space-y-8">
          {quiz.quiz.map((question, index) => {
            const userAnswer = userAnswers[index];
            const correctOption = findCorrectOption(question);
            const isCorrect = isAnswerCorrect(userAnswer, question.answer, question.options);
            
            return (
              <div key={index} className="border border-gray-200 rounded-xl p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h4 className="font-semibold text-gray-900 text-lg mb-2">
                      {index + 1}. {question.question}
                    </h4>
                    <div className="flex items-center space-x-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        question.difficulty === 'easy' ? 'bg-green-100 text-green-800' :
                        question.difficulty === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {question.difficulty}
                      </span>
                      <div className="flex items-center space-x-2">
                        {isCorrect ? (
                          <span className="flex items-center text-green-600 text-sm font-medium">
                            <CheckCircle2 size={16} className="mr-1" />
                            Correct
                          </span>
                        ) : (
                          <span className="flex items-center text-red-600 text-sm font-medium">
                            <XCircle size={16} className="mr-1" />
                            Incorrect
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                
                <div className="space-y-3 mb-4">
                  {question.options.map((option, optIndex) => {
                    const letter = String.fromCharCode(65 + optIndex);
                    const isUserAnswer = option === userAnswer;
                    const isCorrectOption = option === correctOption;
                    
                    let bgColor = 'bg-gray-50 border-gray-200';
                    let textColor = 'text-gray-700';
                    let borderColor = 'border-gray-200';
                    
                    if (isCorrectOption) {
                      bgColor = 'bg-green-50 border-green-300';
                      textColor = 'text-green-800';
                      borderColor = 'border-green-300';
                    }
                    
                    if (isUserAnswer && !isCorrect) {
                      bgColor = 'bg-red-50 border-red-300';
                      textColor = 'text-red-800';
                      borderColor = 'border-red-300';
                    }
                    
                    if (isUserAnswer && isCorrect) {
                      bgColor = 'bg-green-50 border-green-300';
                      textColor = 'text-green-800';
                      borderColor = 'border-green-300';
                    }
                    
                    return (
                      <div
                        key={optIndex}
                        className={`p-4 rounded-lg border-2 ${bgColor} ${borderColor} ${textColor} transition-all duration-200`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center mr-4 font-semibold ${
                              isCorrectOption 
                                ? 'bg-green-500 text-white' 
                                : isUserAnswer && !isCorrect
                                ? 'bg-red-500 text-white'
                                : 'bg-gray-200 text-gray-700'
                            }`}>
                              {letter}
                            </div>
                            <span className={`font-medium ${isCorrectOption ? 'font-bold' : ''}`}>
                              {option}
                            </span>
                          </div>
                          
                          <div className="flex items-center space-x-2">
                            {isCorrectOption && (
                              <div className="flex items-center text-green-600 text-sm font-medium">
                                <CheckCircle2 size={16} className="mr-1" />
                                Correct Answer
                              </div>
                            )}
                            {isUserAnswer && !isCorrect && (
                              <div className="flex items-center text-red-600 text-sm font-medium">
                                <XCircle size={16} className="mr-1" />
                                Your Answer
                              </div>
                            )}
                            {isUserAnswer && isCorrect && (
                              <div className="flex items-center text-green-600 text-sm font-medium">
                                <CheckCircle2 size={16} className="mr-1" />
                                Your Answer ✓
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center mb-2">
                    <span className="text-blue-600 font-semibold">Explanation:</span>
                  </div>
                  <p className="text-blue-800 text-sm leading-relaxed">
                    {question.explanation}
                  </p>
                  
                  {!isCorrect && userAnswer && (
                    <div className="mt-3 pt-3 border-t border-blue-200">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                        <div className="text-red-600">
                          <span className="font-semibold">Your answer:</span> {userAnswer}
                        </div>
                        <div className="text-green-600">
                          <span className="font-semibold">Correct answer:</span> {correctOption}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="card p-6 text-left">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center">
            <BarChart3 size={20} className="mr-2 text-primary-600" />
            Performance Summary
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-600">Accuracy</span>
              <span className="font-semibold">{score.percentage}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Time per Question</span>
              <span className="font-semibold">{formatTime(Math.round(timeElapsed / score.total))}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Difficulty</span>
              <span className="font-semibold capitalize">
                {quiz.quiz.reduce((acc, q) => {
                  acc[q.difficulty] = (acc[q.difficulty] || 0) + 1;
                  return acc;
                }, {})['hard'] > 0 ? 'Mixed' : 
                 quiz.quiz[0]?.difficulty || 'Unknown'}
              </span>
            </div>
          </div>
        </div>

        <div className="card p-6 text-left">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center">
            <Target size={20} className="mr-2 text-primary-600" />
            Next Steps
          </h3>
          <ul className="space-y-2 text-gray-600">
            <li>• Review incorrect answers carefully</li>
            <li>• Focus on questions you got wrong</li>
            <li>• Try again for better score</li>
            <li>• Explore related topics</li>
          </ul>
        </div>
      </div>
    </motion.div>
  );
};

export default FixedQuizTaker;