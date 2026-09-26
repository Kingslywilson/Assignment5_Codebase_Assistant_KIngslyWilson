const { authenticateUser } = require("../services/authService");

async function login(username, password) {
    const user = await authenticateUser(username, password);

    if (!user) {
        return { error: "Invalid credentials" };
    }

    return {
        accessToken: user.accessToken,
        tokenType: "bearer"
    };
}

module.exports = { login };