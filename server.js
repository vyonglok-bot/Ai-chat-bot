const express = require('express');
const { spawn } = require('child_process');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();

// Render द्वारा दिया गया पोर्ट या डिफ़ॉल्ट 3000
const PORT = process.env.PORT || 3000;
// Python सर्वर के लिए एक इंटरनल पोर्ट चुनें
const PYTHON_PORT = 8081; 

// Gunicorn सर्वर को एक सब-प्रोसेस के रूप में शुरू करें
const startPythonServer = () => {
    console.log('Starting Python Gunicorn server...');
    
    // Gunicorn को इंटरनल पोर्ट पर चलाएं
    const pythonServer = spawn('gunicorn', ['app:app', '--bind', `0.0.0.0:${PYTHON_PORT}`]);

    pythonServer.stdout.on('data', (data) => {
        console.log(`[Python STDOUT]: ${data.toString().trim()}`);
    });

    pythonServer.stderr.on('data', (data) => {
        console.error(`[Python STDERR]: ${data.toString().trim()}`);
    });

    pythonServer.on('close', (code) => {
        console.log(`Python server process exited with code ${code}`);
    });
};

// Node सर्वर पर आने वाली सभी API रिक्वेस्ट्स (/api/*) को Python सर्वर पर भेजें
app.use('/api', createProxyMiddleware({
    target: `http://localhost:${PYTHON_PORT}`,
    changeOrigin: true,
}));

// बाकी सभी रिक्वेस्ट्स के लिए static फाइलें (जैसे index.html) सर्व करें
app.use(express.static(__dirname));

// Node.js सर्वर को सुनना शुरू करें
app.listen(PORT, () => {
    console.log(`Node.js wrapper server listening on port ${PORT}`);
    // Node सर्वर शुरू होने के बाद Python सर्वर शुरू करें
    startPythonServer();
});
