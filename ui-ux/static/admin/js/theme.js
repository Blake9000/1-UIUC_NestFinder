// theme.js
const toggle = document.getElementById('theme-toggle');

// Load saved theme or default to auto
const savedTheme = localStorage.getItem('theme') || 'auto';
document.documentElement.setAttribute('data-theme', savedTheme);

toggle?.addEventListener('click', () => {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  let nextTheme;

  if (currentTheme === 'light') nextTheme = 'dark';
  else if (currentTheme === 'dark') nextTheme = 'auto';
  else nextTheme = 'light';

  document.documentElement.setAttribute('data-theme', nextTheme);
  localStorage.setItem('theme', nextTheme);
});