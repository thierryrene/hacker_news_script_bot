document.addEventListener('DOMContentLoaded', () => {
    const glassCard = document.querySelector('.glass-container');

    // Efeito de inclinação (tilt) suave ao passar o mouse
    if (glassCard && window.innerWidth > 900) {
        document.addEventListener('mousemove', (e) => {
            const xAxis = (window.innerWidth / 2 - e.pageX) / 45;
            const yAxis = (window.innerHeight / 2 - e.pageY) / 45;
            glassCard.style.transform = `rotateY(${-xAxis}deg) rotateX(${yAxis}deg) translateY(-8px)`;
        });

        document.addEventListener('mouseleave', () => {
            glassCard.style.transform = `rotateY(-5deg) rotateX(12deg) translateY(0px)`;
        });
    }
});
