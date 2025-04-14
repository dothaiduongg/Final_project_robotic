const os = require('os');

// Hàm lấy địa chỉ IP cục bộ
function getLocalIP() {
    const interfaces = os.networkInterfaces();
    for (let interfaceName in interfaces) {
        for (let iface of interfaces[interfaceName]) {
            if (iface.family === 'IPv4' && !iface.internal) {
                return iface.address; // Trả về địa chỉ IP LAN
            }
        }
    }
    return 'localhost'; // Trả về localhost nếu không tìm thấy
}

// Lấy địa chỉ IP và in ra terminal
const localIP = getLocalIP();
console.log("Địa chỉ IP cục bộ của bạn:", localIP);
