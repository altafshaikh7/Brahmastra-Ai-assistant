import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const authClient = axios.create({
  baseURL: `${BASE_URL}/api/auth`,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const loginUser = async (email, password) => {
  const response = await authClient.post('/login', { email, password });
  return response.data;
};

export const registerUser = async (name, email, password) => {
  const response = await authClient.post('/register', { name, email, password });
  return response.data;
};

export const logoutUser = () => {
  localStorage.removeItem('token');
};

export const getMe = async (token) => {
  const response = await authClient.get('/me', {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return response.data;
};
