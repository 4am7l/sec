const btn = document.getElementById('mainBtn');
const msg = document.getElementById('message');

btn.addEventListener('click', () => {
    msg.textContent = 'Action triggered successfully!';
});
