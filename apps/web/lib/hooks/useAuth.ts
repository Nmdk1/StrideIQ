/**
 * Authentication Hook
 * 
 * Re-exports useAuth from AuthContext for backwards compatibility.
 * All auth state is now shared via React Context.
 */

export { useAuth } from '../context/AuthContext';
export type { AuthState, AuthContextType } from '../context/AuthContext';
