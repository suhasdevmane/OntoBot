// src/pages/Links.js
import React from 'react';
import TopNav from '../components/TopNav';

export default function Links() {
  return (
    <div className="home-body">
      <TopNav />
      <div className="container mt-4">
        <h2>Useful Links</h2>
        <p>Add your own links here (GitHub, research, docs, etc.).</p>
        <ul>
          <li><a href="https://github.com/suhasdevmane/OntoBot" target="_blank" rel="noreferrer">GitHub</a></li>
          <li><a href="https://hub.docker.com/repositories/devmanenvision" target="_blank" rel="noreferrer">Docker Images</a></li>
          <li><a href="https://huggingface.co/suhasdevmane" target="_blank" rel="noreferrer">LLM models</a></li>
          <li><a href="https://ontosage-docs.github.io/" target="_blank" rel="noreferrer">Project Documentation</a></li>
          <li><a href="https://rasa.com/docs/rasa/" target="_blank" rel="noreferrer">Rasa Docs</a></li>
        </ul>
      </div>
    </div>
  );
}
