const { login } = require("./routes/auth");
const { createUser } = require("./routes/users");

function createApplication() {
    return {
        "/login": login,
        "/users": createUser
    };
}

const app = createApplication();

module.exports = app;