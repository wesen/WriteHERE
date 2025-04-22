import React, { useState } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { 
  vscDarkPlus, 
  vs 
} from 'react-syntax-highlighter/dist/esm/styles/prism';

interface CodeHighlighterProps {
  code: string;
  language?: string;
  darkMode?: boolean;
  maxHeight?: string;
  style?: React.CSSProperties;
  showLineNumbers?: boolean;
  wrapLongLines?: boolean;
  showCopyButton?: boolean;
}

const detectLanguage = (code: string): string => {
  // Try to auto-detect JSON
  if (
    (code.trim().startsWith('{') && code.trim().endsWith('}')) ||
    (code.trim().startsWith('[') && code.trim().endsWith(']'))
  ) {
    try {
      JSON.parse(code);
      return 'json';
    } catch (e) {
      // Not valid JSON, continue with other detection
    }
  }

  // Very basic language detection based on common patterns
  if (code.includes('function') && (code.includes('{') || code.includes('=>'))) {
    return 'javascript';
  }
  
  if (code.includes('import ') && code.includes(' from ')) {
    return 'typescript';
  }
  
  if (code.includes('def ') && code.includes(':')) {
    return 'python';
  }

  if (code.includes('<html') || code.includes('<!DOCTYPE')) {
    return 'html';
  }
  
  if (code.includes('SELECT ') || code.includes('FROM ') || code.includes('WHERE ')) {
    return 'sql';
  }

  // Default to text if we can't detect
  return 'text';
};

const CodeHighlighter: React.FC<CodeHighlighterProps> = ({
  code,
  language,
  darkMode = true,
  maxHeight = '400px',
  style = {},
  showLineNumbers = false,
  wrapLongLines = true,
  showCopyButton = true,
}) => {
  const [copySuccess, setCopySuccess] = useState(false);
  
  // Auto detect language if not provided
  const detectedLanguage = language || detectLanguage(code);
  
  const copyToClipboard = () => {
    navigator.clipboard.writeText(code)
      .then(() => {
        setCopySuccess(true);
        setTimeout(() => {
          setCopySuccess(false);
        }, 2000);
      })
      .catch(err => {
        console.error('Failed to copy: ', err);
      });
  };
  
  return (
    <div className="code-highlighter" style={{ position: 'relative' }}>
      {showCopyButton && (
        <button 
          className="copy-button"
          onClick={copyToClipboard}
          aria-label="Copy to clipboard"
        >
          {copySuccess ? 'Copied!' : 'Copy'}
        </button>
      )}
      <SyntaxHighlighter
        language={detectedLanguage}
        style={darkMode ? vscDarkPlus : vs}
        showLineNumbers={showLineNumbers}
        wrapLongLines={wrapLongLines}
        customStyle={{
          borderRadius: '4px',
          fontSize: '0.9em',
          margin: 0,
          maxHeight,
          overflowY: 'auto',
          ...style,
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
};

export default CodeHighlighter; 