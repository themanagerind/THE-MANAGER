import { useRef, useEffect } from 'react';

/**
 * 6-digit OTP input with auto-advance, paste support, backspace handling.
 * Props:
 *   value: string (length 0-6, digits only)
 *   onChange: (string) => void
 *   onComplete?: (string) => void  // fires when 6 digits entered
 *   disabled?: boolean
 *   autoFocus?: boolean
 *   testIdPrefix?: string
 */
const OtpInput = ({
  value = '',
  onChange,
  onComplete,
  disabled = false,
  autoFocus = true,
  testIdPrefix = 'otp',
}) => {
  const refs = useRef([]);

  const digits = value.padEnd(6, ' ').slice(0, 6).split('').map((c) => (c === ' ' ? '' : c));

  useEffect(() => {
    if (autoFocus && refs.current[0]) {
      refs.current[0].focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (value.length === 6 && onComplete) {
      onComplete(value);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const setDigit = (idx, digit) => {
    const arr = digits.slice();
    arr[idx] = digit;
    const next = arr.join('').replace(/\s+/g, '');
    onChange(next);
  };

  const handleChange = (idx, e) => {
    const raw = e.target.value.replace(/\D/g, '');
    if (!raw) {
      setDigit(idx, '');
      return;
    }
    // If user pasted multiple digits in one box
    if (raw.length > 1) {
      const newArr = digits.slice();
      for (let i = 0; i < raw.length && idx + i < 6; i++) {
        newArr[idx + i] = raw[i];
      }
      const next = newArr.join('').replace(/\s+/g, '');
      onChange(next);
      const focusIdx = Math.min(idx + raw.length, 5);
      refs.current[focusIdx]?.focus();
      return;
    }
    setDigit(idx, raw[0]);
    if (idx < 5) refs.current[idx + 1]?.focus();
  };

  const handleKeyDown = (idx, e) => {
    if (e.key === 'Backspace') {
      if (digits[idx]) {
        setDigit(idx, '');
      } else if (idx > 0) {
        refs.current[idx - 1]?.focus();
        setDigit(idx - 1, '');
      }
      e.preventDefault();
    } else if (e.key === 'ArrowLeft' && idx > 0) {
      refs.current[idx - 1]?.focus();
    } else if (e.key === 'ArrowRight' && idx < 5) {
      refs.current[idx + 1]?.focus();
    }
  };

  const handlePaste = (e) => {
    const pasted = (e.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;
    e.preventDefault();
    onChange(pasted);
    const focusIdx = Math.min(pasted.length, 5);
    setTimeout(() => refs.current[focusIdx]?.focus(), 0);
  };

  return (
    <div className="flex gap-2 sm:gap-2.5 justify-between" data-testid={`${testIdPrefix}-container`}>
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <input
          key={i}
          ref={(el) => (refs.current[i] = el)}
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="\d*"
          maxLength={1}
          value={digits[i]}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          disabled={disabled}
          data-testid={`${testIdPrefix}-${i}`}
          className="otp-box"
        />
      ))}
    </div>
  );
};

export default OtpInput;
