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
```**यह फाइल क्या करती है:**
1.  यह `gunicorn app:app` कमांड चलाकर आपके Python ऐप को एक अलग, इंटरनल पोर्ट (`8081`) पर शुरू करती है।
2.  यह एक प्रॉक्सी (proxy) बनाती है। जब आपका `index.html` `/api/chat` या `/api/voices` पर रिक्वेस्ट भेजता है, तो यह Node सर्वर उस रिक्वेस्ट को पकड़कर सीधे आपके Python सर्वर को भेज देता है।
3.  यह `index.html` और अन्य static फाइलों को सीधे सर्व करता है।

#### स्टेप 3: अपनी `app.py` में एक छोटा सा बदलाव

आपको Gunicorn को बताने की ज़रूरत नहीं है कि किस पोर्ट पर चलना है, क्योंकि हम यह `server.js` से कर रहे हैं। सुनिश्चित करें कि आपकी `app.py` फाइल के अंत में यह कोड **न हो** या उसे कमेंट कर दें, क्योंकि Gunicorn सीधे ऐप को चलाएगा।

अपनी `app.py` फाइल के अंत में यह हिस्सा हटा दें या कमेंट कर दें:
```python
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
