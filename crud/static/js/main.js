
const btnDelete= document.querySelectorAll('.btn-borrar');
if(btnDelete) {
  const btnArray = Array.from(btnDelete);
  btnArray.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      if(!confirm('¿Está seguro de querer borrar?')){
        e.preventDefault();
      }
    });
  })
}
const themeSelectors = document.querySelectorAll('.theme-selector');
const themeStylesheet = document.getElementById('theme-stylesheet');
const dropdownButton = document.getElementById('btn-theme-dropdown');

if (themeSelectors.length > 0 && themeStylesheet) {
    // URLs de los temas
    const themes = {
        'light': 'https://bootswatch.com/5/cosmo/bootstrap.min.css',
        'dark': 'https://bootswatch.com/5/darkly/bootstrap.min.css'
    };

    //Textos para el botón principal según el tema
    const themeNames = {
        'light': 'Modo Claro',
        'dark': 'Modo Oscuro'
    };

    //Revisar si hay un tema guardado o aplicar el claro por defecto
    const currentTheme = localStorage.getItem('theme') || 'light';
    
    //Tema inicial al cargar la página
    themeStylesheet.setAttribute('href', themes[currentTheme]);
    dropdownButton.textContent = themeNames[currentTheme];

    //Asignar el evento click a cada opción del menú desplegable
    themeSelectors.forEach(selector => {
        selector.addEventListener('click', (e) => {
            e.preventDefault(); // Evita que la página salte al hacer clic en el enlace '#'
            
            // Obtenemos qué tema eligió leyendo el atributo 'data-theme' del HTML
            const selectedTheme = e.target.getAttribute('data-theme');
            
            // Aplicamos los cambios
            themeStylesheet.setAttribute('href', themes[selectedTheme]);
            dropdownButton.textContent = themeNames[selectedTheme];
            
            // Guardamos la preferencia
            localStorage.setItem('theme', selectedTheme);
        });
    });
}