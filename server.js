const express = require('express');
const nodemailer = require('nodemailer');
const bcrypt = require('bcryptjs');
const cors = require('cors');
const bodyParser = require('body-parser');
require('dotenv').config();

const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5000;
const DB_PATH = path.join(__dirname, 'users.json');

app.use(cors());
app.use(bodyParser.json());
app.use(express.static(__dirname)); // Serve root files like FlowVolt_Dashboard.html

// --- Root Route: Serve the main dashboard ---
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'FlowVolt_Dashboard.html'));
});

// --- Persistent Database Helpers ---
const readUsers = () => {
    if (!fs.existsSync(DB_PATH)) return [];
    try {
        return JSON.parse(fs.readFileSync(DB_PATH));
    } catch (e) {
        return [];
    }
};

const saveUser = (user) => {
    const users = readUsers();
    users.push(user);
    fs.writeFileSync(DB_PATH, JSON.stringify(users, null, 2));
};

const updateUserPassword = (email, newHashedPassword) => {
    const users = readUsers();
    const user = users.find(u => u.email === email);
    if (user) {
        user.password = newHashedPassword;
        fs.writeFileSync(DB_PATH, JSON.stringify(users, null, 2));
    }
};

let pendingVerifications = {}; 

// --- Email Configuration ---
const transporter = nodemailer.createTransport({
    host: 'smtp.gmail.com',
    port: 465,
    secure: true,
    auth: {
        user: process.env.EMAIL_USER,
        pass: process.env.EMAIL_PASS
    }
});

// --- Helper: Generate OTP ---
const generateOTP = () => Math.floor(100000 + Math.random() * 900000).toString();

// --- Helper: Send OTP Email ---
const sendOTPEmail = async (email, otp, subjectType = 'verify') => {
    const subjects = {
        verify: 'Verify Your Email - FlowVolt',
        reset: 'Reset Your Password - FlowVolt',
        resend: 'New Verification Code - FlowVolt'
    };

    const mailOptions = {
        from: `"FlowVolt Security" <${process.env.EMAIL_USER}>`,
        to: email,
        subject: subjects[subjectType],
        html: `
            <div style="font-family: sans-serif; max-width: 500px; margin: auto; padding: 20px; border: 1px solid #1a3a3a; background: #050d0d; color: #e0f5ee; border-radius: 12px;">
                <h2 style="color: #00ff88; text-align: center;">⚡ FlowVolt</h2>
                <p>Hello,</p>
                <p>Your verification code is below. It will expire in <strong>5 minutes</strong>.</p>
                <div style="background: #0a1a1a; padding: 20px; border-radius: 8px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #00ff88; border: 1px solid #1a3a3a;">
                    ${otp}
                </div>
                <p style="font-size: 12px; color: #5a8a7a; margin-top: 20px;">
                    If you did not request this, please ignore this email.
                </p>
            </div>
        `
    };

    try {
        await transporter.sendMail(mailOptions);
        console.log(`[Email] OTP sent to ${email}`);
        return true;
    } catch (error) {
        console.error(`[Email Error] ${error.message}`);
        return false;
    }
};

// --- API: Register ---
app.post('/api/register', async (req, res) => {
    const { name, email, password, nodeType } = req.body;
    const users = readUsers();

    if (users.find(u => u.email === email)) {
        return res.status(400).json({ message: 'User already exists' });
    }

    const otp = generateOTP();
    const expiry = Date.now() + 5 * 60 * 1000; // 5 mins

    pendingVerifications[email] = {
        name,
        email,
        password: await bcrypt.hash(password, 10),
        nodeType,
        otp,
        expiry,
        attempts: 0,
        resends: 0
    };

    const emailSent = await sendOTPEmail(email, otp, 'verify');
    
    // For demo: Log OTP to console if email sending fails
    if (!emailSent) {
        console.log(`[DEMO MODE] Could not send real email. OTP for ${email}: ${otp}`);
    }

    res.json({ message: 'OTP sent to email', email });
});

// --- API: Verify OTP ---
app.post('/api/verify-otp', (req, res) => {
    const { email, otp, type } = req.body; // type: 'register' | 'reset'
    const pending = pendingVerifications[email];

    if (!pending) return res.status(400).json({ message: 'No pending request found' });

    if (Date.now() > pending.expiry) {
        delete pendingVerifications[email];
        return res.status(400).json({ message: 'OTP expired. Please request a new one.' });
    }

    if (pending.otp !== otp) {
        pending.attempts++;
        if (pending.attempts >= 5) {
            delete pendingVerifications[email];
            return res.status(400).json({ message: 'Too many failed attempts. Security lock.' });
        }
        return res.status(400).json({ message: 'Invalid OTP' });
    }

    if (type === 'register') {
        const newUser = {
            id: Date.now(),
            name: pending.name,
            email: pending.email,
            password: pending.password, // already hashed
            nodeType: pending.nodeType
        };
        saveUser(newUser);
        delete pendingVerifications[email];
        res.json({ message: 'Account verified!', user: { name: newUser.name, email: newUser.email, nodeType: newUser.nodeType } });
    } else {
        // Reset mode: just confirm verification for now
        res.json({ message: 'Identity verified. You can now reset your password.' });
    }
});

// --- API: Resend OTP ---
app.post('/api/resend-otp', async (req, res) => {
    const { email } = req.body;
    const pending = pendingVerifications[email];

    if (!pending) return res.status(400).json({ message: 'Session expired. Start over.' });

    if (pending.resends >= 3) {
        return res.status(400).json({ message: 'Max resends reached. Please try later.' });
    }

    const newOtp = generateOTP();
    pending.otp = newOtp;
    pending.expiry = Date.now() + 5 * 60 * 1000;
    pending.resends++;
    pending.attempts = 0;

    await sendOTPEmail(email, newOtp, 'resend');
    res.json({ message: 'New OTP sent', resendsLeft: 3 - pending.resends });
});

// --- API: Login ---
app.post('/api/login', async (req, res) => {
    const { email, password } = req.body;
    const users = readUsers();
    const user = users.find(u => u.email === email);

    if (!user || !(await bcrypt.compare(password, user.password))) {
        return res.status(401).json({ message: 'Invalid credentials' });
    }

    res.json({ message: 'Login successful', user: { name: user.name, email: user.email, nodeType: user.nodeType } });
});

// --- API: Forgot Password ---
app.post('/api/forgot-password', async (req, res) => {
    const { email } = req.body;
    const users = readUsers();
    const user = users.find(u => u.email === email);

    if (!user) return res.status(404).json({ message: 'Email not found' });

    const otp = generateOTP();
    pendingVerifications[email] = {
        email,
        otp,
        expiry: Date.now() + 5 * 60 * 1000,
        attempts: 0,
        resends: 0,
        isReset: true
    };

    await sendOTPEmail(email, otp, 'reset');
    res.json({ message: 'Reset code sent' });
});

// --- API: Reset Password ---
app.post('/api/reset-password', async (req, res) => {
    const { email, otp, newPassword } = req.body;
    const pending = pendingVerifications[email];

    if (!pending || !pending.isReset || pending.otp !== otp) {
        return res.status(400).json({ message: 'Invalid reset attempt' });
    }

    const hashedPwd = await bcrypt.hash(newPassword, 10);
    updateUserPassword(email, hashedPwd);
    delete pendingVerifications[email];

    res.json({ message: 'Password updated successfully' });
});

app.listen(PORT, () => {
    console.log(`[Server] FlowVolt Backend running on http://localhost:${PORT}`);
});
