import loginImg from '../assets/Login/Login_Image.png';
import '../styles/Login.css';
import React, {useState} from 'react';
function Tokens() {
  const [canvasToken, setCanvasToken] = useState('');
  const [navigatorToken, setNavigatorToken] = useState('');
  return (
    <div className="login">
    <div className="login-page">
        <div className="image-container">
            <img src={loginImg} className="login-img" alt="Login Image"/>
        </div>
        <div className="input">
            <input type="text" placeholder="Canvas Token" className="input-field" value={canvasToken} onChange={(e) => setCanvasToken(e.target.value)}/>
            <input type="text" placeholder="Navigator Token" className="input-field" value={navigatorToken} onChange={(e) => setNavigatorToken(e.target.value)}/>
            <button className="login-button">Continue</button>
        </div>
    </div>
    </div>
  );
}
export default Tokens;