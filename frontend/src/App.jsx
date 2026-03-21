import React, { useState, useEffect } from 'react';
import { Brain, Sparkles, History, Home, Menu, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Header from './components/Header';
import Hero from './components/Hero';
import EnhancedGenerateQuizTab from './tabs/EnhancedGenerateQuizTab';
import EnhancedHistoryTab from './tabs/EnhancedHistoryTab';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 10);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const tabs = [
    { id: 'home', label: 'Home', icon: Home },
    { id: 'generate', label: 'Generate Quiz', icon: Sparkles },
    { id: 'history', label: 'History', icon: History },
  ];

  const handleGenerateNewQuiz = () => {
    setActiveTab('generate');
    setMobileMenuOpen(false);
  };

  const handleNavigateToTab = (tabId) => {
    setActiveTab(tabId);
    setMobileMenuOpen(false);
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'home':
        return <Hero onGetStarted={handleGenerateNewQuiz} />;
      case 'generate':
        return <EnhancedGenerateQuizTab />;
      case 'history':
        return <EnhancedHistoryTab onGenerateNewQuiz={handleGenerateNewQuiz} />;
      default:
        return <Hero onGetStarted={handleGenerateNewQuiz} />;
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <motion.header
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled || activeTab !== 'home'
            ? 'bg-white/95 backdrop-blur-lg shadow-lg border-b border-gray-200/50'
            : 'bg-transparent'
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <motion.div
              whileHover={{ scale: 1.05 }}
              className="flex items-center space-x-3 cursor-pointer"
              onClick={() => handleNavigateToTab('home')}
            >
              <div className="relative">
                <div className="w-12 h-12 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center shadow-lg">
                  <Brain className="text-white" size={24} />
                </div>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                  className="absolute -top-1 -right-1 w-6 h-6 bg-gradient-to-r from-amber-400 to-rose-500 rounded-full flex items-center justify-center"
                >
                  <Sparkles size={12} className="text-white" />
                </motion.div>
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-gray-900 to-primary-600 bg-clip-text text-transparent">
                  AI QuizGenius
                </h1>
                <p className="text-xs text-gray-500 font-medium">
                  Transform Articles into Quizzes
                </p>
              </div>
            </motion.div>

            <nav className="hidden md:flex items-center space-x-1 bg-white/80 backdrop-blur-sm rounded-2xl p-1 border border-gray-200/50 shadow-sm">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const isActive = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => handleNavigateToTab(tab.id)}
                    className={`flex items-center space-x-2 px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                      isActive
                        ? 'bg-gradient-to-r from-primary-500 to-primary-600 text-white shadow-lg'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                  >
                    <Icon size={18} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </nav>

            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-xl bg-white/80 backdrop-blur-sm border border-gray-200 shadow-sm"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>

          <AnimatePresence>
            {mobileMenuOpen && (
              <motion.nav
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="md:hidden bg-white/95 backdrop-blur-lg rounded-2xl border border-gray-200/50 shadow-xl mb-4 overflow-hidden"
              >
                <div className="py-2 space-y-1">
                  {tabs.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => handleNavigateToTab(tab.id)}
                        className={`flex items-center space-x-3 w-full px-6 py-4 text-left transition-all duration-200 ${
                          isActive
                            ? 'bg-primary-50 text-primary-600 border-r-4 border-primary-500'
                            : 'text-gray-700 hover:bg-gray-50'
                        }`}
                      >
                        <Icon size={20} />
                        <span className="font-medium">{tab.label}</span>
                      </button>
                    );
                  })}
                </div>
              </motion.nav>
            )}
          </AnimatePresence>
        </div>
      </motion.header>

      <main className="pt-20">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            {renderContent()}
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="bg-gradient-to-br from-gray-900 to-gray-800 text-white py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            <div className="md:col-span-2">
              <div className="flex items-center space-x-3 mb-4">
                <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-2xl flex items-center justify-center">
                  <Brain className="text-white" size={20} />
                </div>
                <div>
                  <h3 className="text-xl font-bold">AI QuizGenius</h3>
                  <p className="text-gray-400 text-sm">Transform Articles into Quizzes</p>
                </div>
              </div>
              <p className="text-gray-400 max-w-md">
                Harness the power of AI to transform Wikipedia articles into engaging, 
                educational quizzes. Learn faster and test your knowledge instantly.
              </p>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-gray-400">
                <li>
                  <button 
                    onClick={handleGenerateNewQuiz}
                    className="hover:text-white transition-colors text-left w-full"
                  >
                    Generate Quiz
                  </button>
                </li>
                <li>
                  <button 
                    onClick={() => handleNavigateToTab('history')}
                    className="hover:text-white transition-colors text-left w-full"
                  >
                    Quiz History
                  </button>
                </li>
                <li>
                  <button 
                    onClick={() => handleNavigateToTab('home')}
                    className="hover:text-white transition-colors text-left w-full"
                  >
                    Features
                  </button>
                </li>
              </ul>
            </div>
            
            <div>
              <h4 className="font-semibold mb-4">Connect</h4>
              <ul className="space-y-2 text-gray-400">
                <li>
                  <a 
                    href="https://github.com" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="hover:text-white transition-colors"
                  >
                    GitHub
                  </a>
                </li>
                <li>
                  <a 
                    href="#" 
                    className="hover:text-white transition-colors"
                  >
                    Documentation
                  </a>
                </li>
                <li>
                  <a 
                    href="#" 
                    className="hover:text-white transition-colors"
                  >
                    Support
                  </a>
                </li>
              </ul>
            </div>
          </div>
          
          <div className="border-t border-gray-700 mt-8 pt-8 text-center text-gray-400">
            <p>&copy; 2024 AI QuizGenius. Built with FastAPI, React, and Google Gemini AI.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;