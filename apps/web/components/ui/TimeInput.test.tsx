/**
 * Tests for TimeInput component
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TimeInput from './TimeInput';

// Mock useId to return consistent values for snapshot stability
jest.mock('react', () => {
  const actual = jest.requireActual('react');
  return {
    ...actual,
    useId: () => ':r0:',  // Match React's actual useId format
  };
});

describe('TimeInput', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    mockOnChange.mockClear();
  });

  describe('rendering', () => {
    it('renders with initial value', () => {
      render(
        <TimeInput value="18:53" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveValue('18:53');
    });

    it('renders with label', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          label="Race Time"
        />
      );
      
      expect(screen.getByLabelText('Race Time')).toBeInTheDocument();
    });

    it('renders with placeholder', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          placeholder="Enter time"
        />
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('placeholder', 'Enter time');
    });

    it('renders error state', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          error="Invalid time"
        />
      );
      
      expect(screen.getByText('Invalid time')).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true');
    });

    it('renders disabled state', () => {
      render(
        <TimeInput 
          value="18:53" 
          onChange={mockOnChange} 
          disabled
        />
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toBeDisabled();
    });

    it('renders required indicator', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          label="Race Time"
          required
        />
      );
      
      expect(screen.getByText('*')).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toHaveAttribute('required');
    });

    it('uses numeric input mode for mobile keyboards', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('inputMode', 'numeric');
    });
  });

  describe('onChange behavior', () => {
    it('calls onChange with formatted and raw values', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '1234' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('12:34', '1234');
    });

    it('strips non-digit characters from input', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: 'abc123' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('1:23', '123');
    });

    it('formats 4 digits as MM:SS', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '1853' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('18:53', '1853');
    });

    it('formats 5 digits as H:MM:SS', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '12345' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('1:23:45', '12345');
    });

    it('formats 6 digits as HH:MM:SS', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '123456' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('12:34:56', '123456');
    });

    it('truncates beyond 6 digits in hhmmss mode', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} maxLength="hhmmss" />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '1234567' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('12:34:56', '123456');
    });

    it('truncates beyond 4 digits in mmss mode', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} maxLength="mmss" />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '12345' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('12:34', '1234');
    });
  });

  describe('real-world race time scenarios', () => {
    it('handles marathon time (4:00:00)', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '40000' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('4:00:00', '40000');
    });

    it('handles 5K time (18:53)', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '1853' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('18:53', '1853');
    });

    it('handles half marathon time (1:30:00)', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '13000' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('1:30:00', '13000');
    });

    it('handles sub-3 marathon (2:59:59)', () => {
      render(
        <TimeInput value="" onChange={mockOnChange} />
      );
      
      const input = screen.getByRole('textbox');
      fireEvent.change(input, { target: { value: '25959' } });
      
      expect(mockOnChange).toHaveBeenCalledWith('2:59:59', '25959');
    });
  });

  describe('accessibility', () => {
    it('associates label with input', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          label="Race Time"
          id="race-time"
        />
      );
      
      const input = screen.getByLabelText('Race Time');
      expect(input).toHaveAttribute('id', 'race-time');
    });

    it('associates error message with input via aria-describedby', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          error="Invalid time"
          id="race-time"
        />
      );
      
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-describedby', 'race-time-error');
    });

    it('marks error message as alert role', () => {
      render(
        <TimeInput 
          value="" 
          onChange={mockOnChange} 
          error="Invalid time"
        />
      );
      
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid time');
    });
  });
});
