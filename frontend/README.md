# Houmy RAG Chatbot Frontend

This is a React TypeScript frontend for the Houmy RAG Chatbot with real-time streaming capabilities.

## 🎯 Streaming Flow Architecture

This frontend implements **real-time text streaming** for AI chat responses. Here's how it works:

### 1. **Streaming Request**
```typescript
const response = await fetch('http://localhost:8001/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: userMessage })
});
```

### 2. **ReadableStream Processing**
```typescript
const reader = response.body!.getReader();
while (true) {
  const { done, value } = await reader.read(); // ← Read chunks as they arrive
  if (done) break;
  // Process chunk immediately...
}
```

### 3. **Server-Sent Events (SSE) Parsing**
```typescript
for (const line of lines) {
  if (line.startsWith('data: ')) {
    const chunk = JSON.parse(line.slice(6));
    if (chunk.type === 'content') {
      appendToMessage(messageId, chunk.content); // ← Live text updates
    }
  }
}
```

### 4. **Real-time UI Updates**
- **Immediate text appending**: Each chunk updates the message instantly
- **Visual feedback**: Blinking cursor and pulsing border during streaming
- **Debug logging**: Console shows every streaming step for debugging

### 🔍 **Debugging Features**
- Comprehensive console logging for each streaming step
- Real-time message count and status display
- Stream cancellation capability
- TypeScript for full type safety

### 🚀 **Key Files**
- `src/components/StreamingChat.tsx` - Main streaming logic
- `src/components/StreamingChat.css` - Streaming visual effects

## Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3001](http://localhost:3001) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can’t go back!**

If you aren’t satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you’re on your own.

You don’t have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn’t feel obligated to use this feature. However we understand that this tool wouldn’t be useful if you couldn’t customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).
