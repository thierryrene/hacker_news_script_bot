document.addEventListener('DOMContentLoaded', () => {
    const glassCard = document.querySelector('.glass-container');

    // Efeito de inclinação (tilt) suave ao passar o mouse
    if (glassCard && window.innerWidth > 900) {
        document.addEventListener('mousemove', (e) => {
            const xAxis = (window.innerWidth / 2 - e.pageX) / 45;
            const yAxis = (window.innerHeight / 2 - e.pageY) / 45;
            glassCard.style.transition = 'none'; // Desabilita transições lentas para acompanhar o mouse instantaneamente
            glassCard.style.transform = `rotateY(${-xAxis}deg) rotateX(${yAxis}deg) translateY(-8px) translateZ(0)`;
        });

        document.addEventListener('mouseleave', () => {
            glassCard.style.transition = 'transform 0.6s cubic-bezier(0.19, 1, 0.22, 1)'; // Reabilita suavidade para o reset
            glassCard.style.transform = `rotateY(-5deg) rotateX(12deg) translateY(0px)`;
        });
    }
});
