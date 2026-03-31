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

    // Carregar o Feed de Notícias JSON
    loadDailyDigest();
});

async function loadDailyDigest() {
    const container = document.getElementById('feed-container');
    const dateLabel = document.getElementById('digest-date-label');
    
    if (!container) return;

    try {
        const response = await fetch('./data/latest.json');
        if (!response.ok) throw new Error('Digest não encontrado ou endpoint indisponível.');
        
        const data = await response.json();
        
        // Atualizar Data
        if (data.updated_at && dateLabel) {
            const dateObj = new Date(data.updated_at);
            dateLabel.innerText = `Atualizado em: ${dateObj.toLocaleDateString('pt-BR')} às ${dateObj.toLocaleTimeString('pt-BR')}`;
        }

        container.innerHTML = '';
        
        data.posts.forEach(post => {
            const card = document.createElement('div');
            card.className = 'feature-card';
            
            // Decidir cor de ícone baseado no ranking
            let colorClass = 'bg-gradient-blue';
            if (post.score > 200) colorClass = 'bg-gradient-orange';
            else if (post.score > 100) colorClass = 'bg-gradient-purple';
            
            card.innerHTML = `
                <div class="feature-icon ${colorClass}" style="margin-bottom: 1rem; font-style: normal;">
                    ${post.emoji || '📰'}
                </div>
                <h3><a href="${post.url}" target="_blank" style="color: inherit; text-decoration: none;">${post.title}</a></h3>
                <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                    ⭐ ${post.score} pontos | <a href="${post.hn_url}" target="_blank" style="color: var(--text-blue); text-decoration: none;">Discussão (HN)</a>
                </div>
                <p><strong>TL;DR:</strong> ${post.tldr || 'Conteúdo sumarizado indisponível.'}</p>
                ${post.insight ? `<p style="margin-top: 0.5rem; color: #d0d0d0;"><strong>Insight:</strong> ${post.insight}</p>` : ''}
                ${post.tags ? `<div style="margin-top: 1rem; font-size: 0.8rem; color: var(--text-orange);">${post.tags}</div>` : ''}
            `;
            container.appendChild(card);
        });

    } catch (err) {
        console.error("Erro ao carregar o feed:", err);
        container.innerHTML = `
            <div class="feature-card" style="grid-column: 1 / -1; text-align: center;">
                <h3 style="margin-bottom: 0.5rem;">Resumos ainda não processados ⏳</h3>
                <p style="color: var(--text-muted);">A rotina de robôs pode ainda estar em confecção ou aguardando disparo. Tente novamente mais tarde.</p>
            </div>
        `;
    }
}
