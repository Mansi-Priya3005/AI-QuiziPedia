import React, { useState } from 'react';
import { 
  Loader2, 
  ExternalLink, 
  Sparkles, 
  CheckCircle2,
  AlertCircle,
  Wand2
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../services/api';
import FixedEnhancedQuizCard from '../components/FixedEnhancedQuizCard';
import LoadingSpinner from '../components/LoadingSpinner';

const EnhancedGenerateQuizTab = () => {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [quiz, setQuiz] = useState(null);
  const [step, setStep] = useState('input');

  const validateUrl = (url) => {
    const wikipediaRegex = /^https:\/\/[a-z]{2,3}\.wikipedia\.org\/wiki\/[^/]+$/;
    return wikipediaRegex.test(url);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setQuiz(null);
    setStep('generating');

    try {
      if (!validateUrl(url)) {
        throw new Error('Please enter a valid Wikipedia URL (e.g., https://en.wikipedia.org/wiki/Artificial_intelligence)');
      }

      const quizData = await api.generateQuiz(url);
      setQuiz(quizData);
      setStep('result');
    } catch (err) {
      setError(err.message || 'Failed to generate quiz. Please try again.');
      setStep('input');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setUrl('');
    setQuiz(null);
    setStep('input');
    setError('');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Generate <span className="gradient-text">AI Quiz</span>
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Paste any Wikipedia article URL and watch as AI transforms it into an engaging educational quiz.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="card p-6 sticky top-8"
            >
              <div className="flex items-center space-x-3 mb-6">
                <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center">
                  <Wand2 className="text-white" size={24} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Create Quiz</h2>
                  <p className="text-gray-600 text-sm">From Wikipedia URL</p>
                </div>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                    Wikipedia Article URL
                  </label>
                  <input
                    type="url"
                    id="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://en.wikipedia.org/wiki/..."
                    className="input-field"
                    disabled={loading}
                  />
                  <p className="text-xs text-gray-500 mt-2">
                    Example: https://en.wikipedia.org/wiki/Artificial_intelligence
                  </p>
                </div>

                <button
                  type="submit"
                  disabled={loading || !url.trim()}
                  className="btn-primary w-full flex items-center justify-center space-x-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      <span>Generating...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={20} />
                      <span>Generate Quiz</span>
                    </>
                  )}
                </button>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="p-4 bg-rose-50 border border-rose-200 rounded-xl flex items-start space-x-3"
                  >
                    <AlertCircle className="text-rose-500 mt-0.5 flex-shrink-0" size={20} />
                    <p className="text-rose-700 text-sm">{error}</p>
                  </motion.div>
                )}
              </form>

              <div className="mt-8 pt-6 border-t border-gray-200">
                <h3 className="font-semibold text-gray-900 mb-4">What you'll get:</h3>
                <div className="space-y-3">
                  {[
                    '5-10 AI-generated questions',
                    'Multiple difficulty levels',
                    'Detailed explanations',
                    'Key entities extraction',
                    'Related topics for learning'
                  ].map((feature, index) => (
                    <div key={index} className="flex items-center space-x-3">
                      <CheckCircle2 className="text-emerald-500 flex-shrink-0" size={18} />
                      <span className="text-sm text-gray-600">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          </div>

          <div className="lg:col-span-2">
            <AnimatePresence mode="wait">
              {step === 'generating' && (
                <motion.div
                  key="generating"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="card p-12 text-center"
                >
                  <LoadingSpinner size="xl" text="AI is generating your quiz..." />
                  
                  <div className="mt-8 grid grid-cols-3 gap-4 max-w-md mx-auto">
                    {[
                      { text: 'Scraping Article', color: 'bg-blue-500' },
                      { text: 'Analyzing Content', color: 'bg-purple-500' },
                      { text: 'Generating Quiz', color: 'bg-primary-500' }
                    ].map((stepItem, index) => (
                      <div key={index} className="text-center">
                        <div className={`w-3 h-3 ${stepItem.color} rounded-full animate-pulse mx-auto mb-2`}></div>
                        <p className="text-xs text-gray-600">{stepItem.text}</p>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}

              {step === 'result' && quiz && (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                >
                  <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold text-gray-900">
                      Quiz Generated Successfully! 🎉
                    </h2>
                    <button
                      onClick={resetForm}
                      className="btn-secondary"
                    >
                      Create New Quiz
                    </button>
                  </div>
                  <FixedEnhancedQuizCard quiz={quiz} mode="view" />
                </motion.div>
              )}

              {step === 'input' && !quiz && (
                <motion.div
                  key="empty"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="card p-12 text-center"
                >
                  <div className="w-24 h-24 bg-gradient-to-br from-gray-200 to-gray-300 rounded-3xl flex items-center justify-center mx-auto mb-6">
                    <Sparkles className="text-gray-400" size={40} />
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900 mb-4">
                    Ready to Generate Magic?
                  </h3>
                  <p className="text-gray-600 max-w-md mx-auto mb-8">
                    Enter a Wikipedia URL above and watch as AI transforms it into an engaging educational quiz with questions, explanations, and key insights.
                  </p>
                  
                  <div className="max-w-md mx-auto">
                    <p className="text-sm font-medium text-gray-700 mb-3">Try these examples:</p>
                    <div className="space-y-2">
                      {[
                        'https://en.wikipedia.org/wiki/Artificial_intelligence',
                        'https://en.wikipedia.org/wiki/Renaissance',
                        'https://en.wikipedia.org/wiki/Quantum_mechanics'
                      ].map((sampleUrl, index) => (
                        <button
                          key={index}
                          onClick={() => setUrl(sampleUrl)}
                          className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-xl text-sm text-gray-600 transition-colors duration-200"
                        >
                          {sampleUrl}
                        </button>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EnhancedGenerateQuizTab;