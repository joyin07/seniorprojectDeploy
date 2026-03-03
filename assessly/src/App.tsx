import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './styles/App.css'
import { HashRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/dashboard'
import Login from './pages/login';
import AddCourses from './pages/addCourses';
import Tokens from './pages/tokens';


function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/login" element={<Login />} /> 
        <Route path="/tokens" element={<Tokens />} /> 
        <Route path="/add-courses" element={<AddCourses />} /> 
      </Routes>
    </HashRouter>
  )
}
export default App

// Testing 
// http://localhost:<your local host num>/#/login
