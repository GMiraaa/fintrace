import React from 'react'
import ReactDOM from 'react-dom/client'
import '@fontsource-variable/ibm-plex-sans'
import App from './App'
import './styles.css'

const root = document.getElementById('root')

if (!root) throw new Error('Elemento raiz da aplicação não encontrado.')

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
