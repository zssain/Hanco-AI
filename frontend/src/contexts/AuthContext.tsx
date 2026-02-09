import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  onAuthStateChanged,
  signOut as firebaseSignOut,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from 'firebase/auth';
import { auth } from '@/lib/firebase';
import api from '@/lib/api';

interface UserProfile {
  uid: string;
  email: string;
  full_name: string;
  phone: string;
  role: string;
  is_active: boolean;
}

interface AuthContextType {
  user: User | null;
  userProfile: UserProfile | null;
  loading: boolean;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string, phone: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Real Firebase authentication (mock user removed for security)
  const [user, setUser] = useState<User | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch user profile from backend
  const fetchUserProfile = async (firebaseUser: User) => {
    try {
      // GUEST MODE: Backend auth endpoints removed
      // Just set a basic profile from Firebase user data
      setUserProfile({
        uid: firebaseUser.uid,
        email: firebaseUser.email || '',
        full_name: firebaseUser.displayName || 'Guest User',
        role: 'consumer',
        phone: '',
        is_active: true
      });
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
      setUserProfile(null);
    }
  };

  // Real Firebase auth listener (previously disabled)
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      if (firebaseUser) {
        await fetchUserProfile(firebaseUser);
      } else {
        setUserProfile(null);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const login = async (email: string, password: string) => {
    try {
      // Sign in with Firebase
      const userCredential = await signInWithEmailAndPassword(auth, email, password);
      const firebaseUser = userCredential.user;
      
      // GUEST MODE: No backend sync, just use Firebase user
      setUserProfile({
        uid: firebaseUser.uid,
        email: firebaseUser.email || '',
        full_name: firebaseUser.displayName || 'User',
        role: 'consumer',
        phone: '',
        is_active: true
      });
    } catch (error: any) {
      console.error('Login error:', error);
      throw new Error(error.response?.data?.detail || error.message || 'Login failed');
    }
  };

  const register = async (email: string, password: string, fullName: string, phone: string) => {
    try {
      // Create user in Firebase
      await createUserWithEmailAndPassword(auth, email, password);
      
      // Register with backend
      const response = await api.post('/auth/register', {
        email,
        full_name: fullName,
        phone_number: phone,
        role: 'consumer',
      });
      
      setUserProfile(response.data);
    } catch (error: any) {
      console.error('Registration error:', error);
      // If Firebase account was created but backend failed, clean up
      if (auth.currentUser) {
        await auth.currentUser.delete().catch(console.error);
      }
      throw new Error(error.response?.data?.detail || error.message || 'Registration failed');
    }
  };

  const logout = async () => {
    try {
      await firebaseSignOut(auth);
      setUserProfile(null);
    } catch (error) {
      console.error('Logout error:', error);
      throw error;
    }
  };

  const isAdmin = userProfile?.role === 'admin';

  return (
    <AuthContext.Provider value={{ user, userProfile, loading, isAdmin, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
